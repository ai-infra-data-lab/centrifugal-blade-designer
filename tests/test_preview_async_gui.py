import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import time
import numpy as np
import pytest
from PySide6.QtCore import QObject,Signal,QTimer,QProcess,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtTest import QTest
from shiboken6 import isValid,delete

from blade_designer.gui.main_window import MainWindow
from blade_designer.gui.preview_worker import PreviewWorker
from blade_designer.fileio.preview_job import queue_preview,calculate_preview
from blade_designer.models.parameters import BladeParameters
from test_contextual_3d_gui import assigned_project


class HeldWorker(QObject):
    completed=Signal(object)
    def __init__(self,job,parent=None):
        super().__init__(parent);self.job=job;self.cancelled=False;self.started=False;self.done=False
    def start(self):self.started=True
    def cancel(self):self.cancelled=True
    def finish(self):
        assert not self.done;self.done=True
        self.completed.emit({'overall':'FAIL','cancelled':True} if self.cancelled else calculate_preview(self.job))


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.set_parameters(assigned_project());w.update_geometry();w._reset_history();w.timer.stop()
    w._preview_controller.worker_factory=HeldWorker
    yield w
    if isValid(w):
        w.timer.stop();worker=w._preview_controller.worker
        w.close()
        if worker is not None and not worker.done:worker.finish()
        app.processEvents();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()


def edit(window,delta):
    box=window.angle_editor.table.cellWidget(1,1)
    box.setValue(box.value()+delta);box.editingFinished.emit();window.timer.stop()


def test_debounced_timer_uses_process_and_keeps_previous_model_until_ready(window):
    w=window;old=w._selected_3d_geometry;camera=deepcopy(w.model_preview_3d.camera_position)
    edit(w,-2);w.timer.timeout.emit()
    worker=w._preview_controller.worker
    assert worker.started and w._preview_pending and w._selected_3d_geometry is old
    assert w.row_metrics_widget.source is None and w.passage_widget.source is None
    assert not w.flow_area_widget.isEnabled() and 'actual' not in w.geometry_sources
    assert 'legacy' not in w.geometry_sources and not w.metrics_widget.isEnabled() and not w.curvature_plot.isEnabled()
    before=deepcopy(w.get_parameters());worker.finish()
    assert not w._preview_pending and not w._preview_controller.busy
    assert w._selected_3d_geometry is not old and w.flow_area_widget.isEnabled()
    assert w.metrics_widget.isEnabled() and w.curvature_plot.isEnabled()
    assert w.row_metrics_widget.geometry is w._selected_3d_geometry and w.passage_widget.source[0] is w._selected_3d_geometry
    assert w.get_parameters()==before
    for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)


def test_repeated_edits_keep_one_active_and_only_the_latest_pending_request(window):
    w=window;old=w._selected_3d_geometry
    w._queue_preview_update();first=w._preview_controller.worker
    edit(w,-1);w._queue_preview_update();second_generation=w._preview_generation
    edit(w,-2);w._queue_preview_update()
    assert w._preview_controller.worker is first and first.cancelled
    assert w._preview_controller.pending.generation>second_generation
    expected=deepcopy(w.get_parameters());first.finish()
    latest=w._preview_controller.worker
    assert latest is not first and w._selected_3d_geometry is old
    latest.finish()
    assert w.get_parameters()==expected and not w._preview_controller.busy
    np.testing.assert_array_equal(w.blade_plot.curves['PS'].xData,w._selected_3d_geometry.sections[0].master_ps.x)


def test_uncommitted_text_alone_discards_the_result(window):
    w=window;field=QLineEdit(w);old=w._selected_3d_geometry;params=deepcopy(w.get_parameters())
    w._queue_preview_update();worker=w._preview_controller.worker
    field.setText('not yet confirmed');worker.finish()
    assert w.get_parameters()==params and w._selected_3d_geometry is old
    assert w.row_metrics_widget.source is None and 'outdated preview discarded' in w.statusBar().currentMessage()


def test_retired_table_fields_do_not_discard_an_unchanged_design(window):
    w=window;field=QLineEdit(w);old=w._selected_3d_geometry
    w._queue_preview_update();worker=w._preview_controller.worker
    field.deleteLater();QCoreApplication.sendPostedEvents(field,QEvent.Type.DeferredDelete)
    worker.finish()
    assert w._selected_3d_geometry is not old and w.row_metrics_widget.source is not None


def test_explicit_synchronous_api_invalidates_pending_background_work(window):
    w=window;w._queue_preview_update();worker=w._preview_controller.worker
    edit(w,-1);w.update_geometry();current=w._selected_3d_geometry
    assert worker.cancelled and not w._preview_pending
    worker.finish()
    assert w._selected_3d_geometry is current and not w._preview_controller.busy


def test_meridional_selection_uses_prepared_all_rows_without_gui_regeneration(window,monkeypatch):
    w=window;w.navigator.meridionalSelected.emit();worker=w._preview_controller.worker
    assert w._editing_meridional and worker is not None
    def forbidden(*args):raise AssertionError('GUI repeated numeric generation')
    monkeypatch.setattr(w.designer,'generate_3d',forbidden)
    monkeypatch.setattr(w.designer,'generate_diffuser_3d',forbidden)
    worker.finish()
    assert not w._preview_pending and not w._central_preview_errors
    assert 'All blade rows (2)' in w.model_preview_3d.model_label
    assert 'Impeller [row-1] Hub camber' in w.model_preview_3d.base_lines
    assert 'Diffuser [row-2] Hub camber' in w.model_preview_3d.base_lines


def test_row_selection_during_another_request_adopts_only_selected_stator(window):
    w=window;w._queue_preview_update();old=w._preview_controller.worker
    w.navigator.rowSelected.emit('row-2')
    assert w._active_row=='row-2' and old.cancelled
    old.finish();w._preview_controller.worker.finish()
    assert w._selected_3d_geometry is w.diffuser_geometry
    assert w.row_metrics_widget.source.row_id=='row-2'
    assert w.passage_widget.source[0] is w.diffuser_geometry


def test_display_switches_do_not_duplicate_the_pending_calculation(window):
    w=window;w._queue_preview_update();worker=w._preview_controller.worker
    w.annulus_3d.setChecked(True);w.annulus_2d.setChecked(True)
    assert w._preview_controller.worker is worker and w._preview_controller.pending is None
    worker.finish();assert w.annulus_2d.isChecked() and w.annulus_3d.isChecked()


def test_gui_undo_redo_preserves_design_and_uses_latest_generation(window,tmp_path):
    w=window;before=deepcopy(w.get_parameters());edit(w,-2);changed=deepcopy(w.get_parameters())
    assert w.undo_stack.canUndo()
    w._queue_preview_update();old=w._preview_controller.worker
    w.undo_action.trigger();assert w.get_parameters()==before and old.cancelled
    old.finish();w._preview_controller.worker.finish()
    w.redo_action.trigger();assert w.get_parameters()==changed
    w._preview_controller.worker.finish()
    assert w.get_parameters()==changed and w.row_metrics_widget.source is not None
    path=tmp_path/'design.json';w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters()==changed


def test_cancel_menu_discards_pending_results_and_keeps_stop_confirmation_explicit(window):
    w=window;old=w._selected_3d_geometry
    assert w.cancel_preview_action in w.edit_menu.actions() and not w.cancel_preview_action.isEnabled()
    w._queue_preview_update();worker=w._preview_controller.worker
    assert w.cancel_preview_action.isEnabled();w.cancel_preview_action.trigger()
    assert worker.cancelled and not w._preview_pending
    worker.finish()
    assert w._selected_3d_geometry is old and not w.cancel_preview_action.isEnabled()
    assert 'not confirmed' in w.statusBar().currentMessage()


def test_worker_timeout_clears_pending_state_and_does_not_report_success(window):
    w=window;old=w._selected_3d_geometry;w._queue_preview_update()
    worker=w._preview_controller.worker;worker.cancel();worker.finish()
    assert not w._preview_pending and w._selected_3d_geometry is old
    assert 'ERROR' in w.messages.toPlainText() and w.row_metrics_widget.source is None


def test_new_request_after_cancel_does_not_inherit_the_cancelled_status(window):
    w=window;w._queue_preview_update();old=w._preview_controller.worker
    w.cancel_preview_action.trigger();w._queue_preview_update();old.finish()
    w._preview_controller.worker.finish()
    assert w.row_metrics_widget.source is not None and 'discarded' not in w.statusBar().currentMessage()


def test_deferred_delete_waits_for_both_preview_and_cad_and_handles_duplicate_close_callbacks(window):
    w=window;w._queue_preview_update();preview=w._preview_controller.worker
    cad=HeldWorker(None,w);w._cad_worker=cad
    w.deleteLater();QCoreApplication.sendPostedEvents(w,QEvent.Type.DeferredDelete)
    assert isValid(w) and preview.cancelled and cad.cancelled
    cad.completed.emit({'overall':'FAIL','cancelled':True});preview.finish()
    QTest.qWait(30);QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    assert not isValid(w)


@pytest.mark.parametrize('action',['close','deferred_delete','forced_delete'])
def test_window_lifecycle_cancels_owned_work_without_destroying_an_active_process(window,action):
    w=window;w.show();w._queue_preview_update();controller=w._preview_controller;worker=controller.worker
    if action=='close':
        w.close();assert isValid(w) and w.isVisible()
    elif action=='deferred_delete':
        w.deleteLater();QCoreApplication.sendPostedEvents(w,QEvent.Type.DeferredDelete);assert isValid(w)
    else:
        delete(w);assert not isValid(w) and isValid(controller)
    assert worker.cancelled and controller.pending is None
    worker.finish();QTest.qWait(30);QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    if action=='close':assert not w.isVisible()
    else:assert not isValid(w)


@pytest.mark.parametrize('failure',['numerical','execution','corrupt_payload'])
def test_failed_background_result_preserves_frame_and_invalidates_current_measurements(window,failure):
    w=window;old=w._selected_3d_geometry
    if failure=='numerical':
        w.meridional_editor.blade_edges.row_controls['row-1','trailing_edge','hub'].setValue(.01)
    w._queue_preview_update();worker=w._preview_controller.worker
    if failure=='execution':worker.completed.emit({'overall':'FAIL','error':{'message':'worker failed'}})
    elif failure=='corrupt_payload':
        report=calculate_preview(worker.job);(worker.job/'payload.json').write_text('{}')
        worker.completed.emit(report)
    else:worker.finish()
    assert w._selected_3d_geometry is old and w.row_metrics_widget.source is None and w.passage_widget.source is None
    assert 'ERROR' in w.messages.toPlainText() and not w.flow_area_widget.isEnabled()


@pytest.mark.parametrize('action',['complete','cancel','missing_python'])
def test_real_worker_completion_tree_cancel_and_launch_failure(tmp_path,monkeypatch,action):
    app=QApplication.instance() or QApplication([])
    job=queue_preview(BladeParameters(),'impeller',False,tmp_path/'job');worker=PreviewWorker(job)
    if action=='missing_python':
        launch=worker._launch
        monkeypatch.setattr(worker,'_launch',lambda python,module,phase:launch(str(tmp_path/'absent.exe'),module,phase))
    reports=[];worker.completed.connect(reports.append)
    if action=='cancel':worker.process.started.connect(lambda:QTimer.singleShot(100,worker.cancel))
    begin=time.monotonic();worker.start();assert time.monotonic()-begin<1.
    deadline=time.monotonic()+30
    while not reports and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    assert len(reports)==1 and worker.process.state()==QProcess.ProcessState.NotRunning
    if action=='complete':assert reports[0]['phase']=='PREVIEW_READY'
    else:
        assert reports[0]['overall']=='FAIL'
        if action=='cancel':assert reports[0]['cancelled'] and reports[0]['termination_status']=='PROCESS_TREE_STOPPED'
        else:assert reports[0]['error']['type']=='PreviewError'
    worker.deleteLater();app.processEvents()
