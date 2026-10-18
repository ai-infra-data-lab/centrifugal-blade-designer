import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.cad_surface_reference_widget import CadSurfaceReferenceWidget
from blade_designer.models.parameters import BladeParameters,SplitterParameters,ImpellerTrimParameters


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def test_reference_is_read_only_and_density_group_keep_camera(app,monkeypatch):
    p=BladeParameters();p.splitter=SplitterParameters();before=deepcopy(p)
    widget=CadSurfaceReferenceWidget(lambda:p)
    def forbidden(*args,**kwargs):raise AssertionError('Reference must not write files or run CAD')
    from blade_designer.cad import client
    monkeypatch.setattr(client,'prepare_job',forbidden)
    for name in ('mkdir','write_text','write_bytes'):monkeypatch.setattr(Path,name,forbidden)
    try:
        widget.resize(850,650);widget.show();widget.refresh();app.processEvents()
        assert widget.result is not None and not widget.preview.isHidden()
        assert 'Snapshot:' in widget.info.text() and 'BREP' in widget.info.text()
        widget.preview._show_fit.stop()
        widget.preview.camera_position['azimuth']=73.;widget.preview.camera_position['scale']=95.
        camera=deepcopy(widget.preview.camera_position)
        widget.density.setCurrentText('129');widget.group.setCurrentIndex(1);app.processEvents()
        assert 'Splitter' in widget.info.text() and '129' in widget.info.text()
        for key,value in camera.items():np.testing.assert_array_equal(widget.preview.camera_position[key],value)
        widget.full.setChecked(True)
        assert widget.preview.full_annulus and widget.preview.blade_count==p.geometry.vane_count
        widget.refresh();app.processEvents()
        for key,value in camera.items():np.testing.assert_array_equal(widget.preview.camera_position[key],value)
        assert p==before
        widget.invalidate();assert widget.result is None and widget.preview.isHidden()
    finally:widget.close();widget.deleteLater();app.processEvents()


@pytest.mark.parametrize('bad',['selection','trim','invalid','stator'])
def test_unsupported_or_invalid_reference_clears_previous_preview(app,bad):
    current=[BladeParameters()];widget=CadSurfaceReferenceWidget(lambda:current[0])
    try:
        widget.refresh();assert widget.result is not None
        if bad=='selection':current[0]=None
        elif bad=='trim':current[0].impeller_trim=ImpellerTrimParameters(10)
        elif bad=='invalid':current[0].hub.segments[0].length=-1
        else:
            from blade_designer.fileio.project_io import load_project
            current[0]=load_project(Path(__file__).resolve().parents[1]/'blade_designer/defaults/default_project.json')
        widget.refresh();assert widget.result is None and widget.preview.isHidden()
        assert '作成できません' in widget.info.text()
    finally:widget.close();widget.deleteLater();app.processEvents()


def test_menu_keeps_main_design_history_camera_and_invalidates_reference(app):
    from blade_designer.gui.main_window import MainWindow
    from test_standard_menus_gui import dispose
    w=MainWindow()
    try:
        w.timer.stop();before=deepcopy(w.get_parameters());history=w.undo_stack.count()
        camera=deepcopy(w.model_preview_3d.camera_position)
        next(a for a in w.view_menu.actions() if a.text()=='CAD Surface Reference').trigger()
        widget=w.cad_surface_reference_widget;assert widget.result is not None
        assert w.get_parameters()==before and w.undo_stack.count()==history
        for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)
        assert w.show_cad_surface_reference() is w._tool_dialogs['CAD Surface Reference']
        w._select_meridional();assert widget.result is None and widget.preview.isHidden()
        widget.refresh();assert widget.result is None
    finally:dispose(w,app)


def test_legacy_stator_selection_cannot_open_an_impeller_reference(app):
    from blade_designer.gui.main_window import MainWindow
    from test_standard_menus_gui import dispose
    w=MainWindow()
    try:
        assert w._blade_rows is None
        w.view_mode.setCurrentIndex(1);w.timer.stop()
        before=deepcopy(w.get_parameters());history=w.undo_stack.count()
        w.show_cad_surface_reference();widget=w.cad_surface_reference_widget
        assert widget.result is None and widget.preview.isHidden()
        assert 'Impeller専用' in widget.info.text()
        assert w.get_parameters()==before and w.undo_stack.count()==history
    finally:dispose(w,app)
