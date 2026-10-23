import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import time
import pytest
from PySide6.QtCore import QObject,Signal,QProcess
from PySide6.QtWidgets import QApplication
from blade_designer.gui import main_window
from blade_designer.cad.provisional_disk_job import calculate_disk


class HeldWorker(QObject):
    progress=Signal(str);completed=Signal(object)
    def __init__(self,job,parent):super().__init__(parent);self.job=job;self.started=False
    def start(self):self.started=True
    def cancel(self):self.completed.emit({'overall':'FAIL','cancelled':True,'artifacts':{}})


@pytest.fixture
def window(monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window,'ProvisionalDiskWorker',HeldWorker)
    w=main_window.MainWindow();w.show();app.processEvents()
    yield app,w
    w.timer.stop();w.close();app.processEvents();w.deleteLater();app.processEvents()


@pytest.mark.parametrize('change',['committed','uncommitted','selection','cancel','bad_result'])
def test_stale_text_selection_cancel_and_bad_result_never_start_cad(window,monkeypatch,change):
    app,w=window;before=deepcopy(w.get_parameters());calls=[]
    monkeypatch.setattr(main_window,'CadExportWorker',lambda *args:calls.append(args))
    w.start_cad_job('generate');worker=w._cad_worker
    assert worker.started and w.get_parameters()==before
    if change=='committed':w.cad_editor.radius.setValue(2.5)
    elif change=='uncommitted':w.cad_editor.radius.lineEdit().setText('2.75')
    elif change=='selection':w._select_meridional()
    elif change=='cancel':worker.cancel();assert w._cad_worker is None;return
    if change=='bad_result':report={'overall':'PASS','artifacts':{}}
    else:report=calculate_disk(worker.job)
    worker.completed.emit(report)
    assert not calls and w._cad_worker is None
    assert w.get_parameters().cad_export.disk==before.cad_export.disk
    if change=='uncommitted':assert w.cad_editor.radius.lineEdit().text()=='2.75'


def test_success_adopts_disk_once_and_continues_original_action_and_target(window,monkeypatch,tmp_path):
    from blade_designer.cad import client
    import json
    app,w=window;before=deepcopy(w.get_parameters());jobs=[];published=[]
    class CadWorker(HeldWorker):
        def start(self):jobs.append(self.job);self.completed.emit({'overall':'WARNING','artifacts':{}})
    monkeypatch.setattr(main_window,'CadExportWorker',CadWorker)
    def publish(job,target,params):
        published.append((job,target));return {'overall':'WARNING','artifacts':{}}
    monkeypatch.setattr(client,'publish_job',publish)
    w.start_cad_job('mechanical',tmp_path/'case');worker=w._cad_worker
    assert not jobs
    worker.completed.emit(calculate_disk(worker.job))
    assert len(jobs)==1 and w.get_parameters().cad_export.disk.provisional
    assert published==[(jobs[0],tmp_path/'case')]
    assert json.loads((jobs[0]/'request.json').read_text())['action']=='mechanical'
    w.undo();assert w.get_parameters()==before
    assert not (tmp_path/'case').exists()


def test_close_cancels_disk_preparation_without_starting_cad(window):
    app,w=window;w.start_cad_job('generate');worker=w._cad_worker
    w.close();app.processEvents()
    assert w._cad_worker is None and w._cad_closing and not w.isVisible()


def test_real_worker_process_finishes_without_importing_a_cad_backend(tmp_path):
    from blade_designer.gui.provisional_disk_worker import ProvisionalDiskWorker
    from blade_designer.cad.provisional_disk_job import queue_disk_job
    from blade_designer.models.parameters import BladeParameters
    app=QApplication.instance() or QApplication([])
    worker=ProvisionalDiskWorker(queue_disk_job(BladeParameters(),tmp_path/'job'))
    reports=[];worker.completed.connect(reports.append);worker.start();deadline=time.monotonic()+30
    while not reports and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    assert len(reports)==1 and reports[0]['phase']=='PROVISIONAL_DISK_READY'
    assert worker._completed and worker.process.state()==QProcess.ProcessState.NotRunning
    worker.deleteLater();app.processEvents()


@pytest.mark.parametrize('failure',['cancel','missing_python'])
def test_real_worker_cancel_or_launch_failure_finishes_without_adoption(tmp_path,monkeypatch,failure):
    from blade_designer.gui.provisional_disk_worker import ProvisionalDiskWorker
    from blade_designer.cad.provisional_disk_job import queue_disk_job
    from blade_designer.models.parameters import BladeParameters
    app=QApplication.instance() or QApplication([])
    worker=ProvisionalDiskWorker(queue_disk_job(BladeParameters(),tmp_path/'job'))
    if failure=='missing_python':
        launch=worker._launch
        monkeypatch.setattr(worker,'_launch',lambda python,module,phase:launch(str(tmp_path/'missing-python.exe'),module,phase))
    reports=[];worker.completed.connect(reports.append);worker.start();deadline=time.monotonic()+30
    if failure=='cancel':
        while worker.process.state()==QProcess.ProcessState.Starting and time.monotonic()<deadline:app.processEvents()
        worker.cancel()
    while not reports and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    assert len(reports)==1 and reports[0]['overall']=='FAIL' and worker._completed
    assert worker.process.state()==QProcess.ProcessState.NotRunning
    if failure=='cancel':
        assert reports[0]['cancelled'] and reports[0]['termination_status']=='PROCESS_TREE_STOPPED'
    else:assert reports[0]['error']['type']=='CadExportError'
    worker.deleteLater();app.processEvents()
