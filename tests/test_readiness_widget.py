import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.cad import MechanicalExportScope
from blade_designer.gui.export_readiness_widget import ExportReadinessWidget


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def test_refresh_is_read_only_and_distinguishes_kernel_from_inputs(app,monkeypatch):
    p=BladeParameters();p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    before=deepcopy(p);widget=ExportReadinessWidget(lambda:p)
    def forbidden(*args,**kwargs):raise AssertionError('diagnostic cannot write files')
    for name in ('mkdir','write_text','write_bytes'):monkeypatch.setattr(Path,name,forbidden)
    try:
        widget.show();app.processEvents();QTest.mouseClick(widget.refresh_button,Qt.MouseButton.LeftButton)
        assert widget.result is not None and widget.text.isReadOnly()
        text=widget.text.toPlainText()
        assert 'Profile Points' in text and 'CAD生成は未実施' in text and 'ANSYS Import / Mesh: NOT_TESTED' in text
        assert p==before
        widget.invalidate();assert widget.result is None and '再診断' in widget.text.toPlainText()
    finally:widget.close();widget.deleteLater();app.processEvents()


def test_no_selection_or_invalid_input_clears_previous_result(app):
    data=[BladeParameters()];widget=ExportReadinessWidget(lambda:data[0])
    try:
        widget.refresh();assert widget.result is not None
        data[0]=None;widget.refresh();assert widget.result is None and '翼列' in widget.text.toPlainText()
        data[0]=BladeParameters();data[0].hub.segments[0].length=-1
        widget.refresh();assert widget.result is not None
        assert all(route.status=='BLOCKED' for route in widget.result.routes)
    finally:widget.close();widget.deleteLater();app.processEvents()


def test_main_window_menu_preserves_design_history_camera_and_reuses_dialog(app,monkeypatch):
    import numpy as np
    from blade_designer.gui.main_window import MainWindow
    from blade_designer.cad import client
    from test_standard_menus_gui import dispose
    def forbidden(*args,**kwargs):raise AssertionError('Diagnostics must not start a CAD job')
    monkeypatch.setattr(client,'prepare_job',forbidden)
    from blade_designer.fileio.project_io import load_project
    w=MainWindow(default_parameters=load_project(Path(__file__).resolve().parents[1]/"blade_designer/defaults/default_project.json"))
    try:
        w.select_blade_row("row-3");w.timer.stop()
        before=deepcopy(w.get_parameters());history=w.undo_stack.count()
        camera=deepcopy(w.model_preview_3d.camera_position)
        menu=next(a.menu() for a in w.file_menu.actions() if a.text()=='Export')
        next(a for a in menu.actions() if a.text()=='Export Readiness').trigger()
        widget=w.export_readiness_widget
        assert widget.result.row_name=='RC'
        assert w.get_parameters()==before and w.undo_stack.count()==history
        for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)
        dialog=w._tool_dialogs['Export Readiness']
        assert w.show_export_readiness() is dialog
        w.select_blade_row('row-1')
        assert widget.result is None
        widget.refresh();assert widget.result.row_name=='Impeller'
        w.cad_editor.radius.setValue(2.)
        assert widget.result is None
        widget.refresh();assert widget.result is not None
        w.output_editor.controls['geometry_unit'].setCurrentText('CM')
        assert widget.result is None
        widget.refresh();w._select_meridional()
        assert widget.result is None
        widget.refresh();assert widget.result is None and '翼列' in widget.text.toPlainText()
    finally:dispose(w,app)
