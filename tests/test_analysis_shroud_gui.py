import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow
from blade_designer.gui.coordinate_export_dialog import CoordinateExportDialog
from test_analysis_shroud import parameters
from test_standard_menus_gui import dispose


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow(default_parameters=parameters());w.show();app.processEvents();w.timer.stop()
    yield w
    dispose(w,app)


def enable(w):
    e=w.tip_clearance_editor;e.setChecked(True)
    e.controls['le_mm'].setValue(.5);e.controls['te_mm'].setValue(.5);w.update_geometry()
    return e


def test_controls_fixed_tip_both_previews_history_and_json(window,tmp_path):
    w=window;e=enable(w);baseline=deepcopy(w.get_parameters())
    tip=w.impeller_geometry.sections[-1].master_ps.xyz.copy()
    camera=deepcopy(w.model_preview_3d.camera_position)
    e.analysis_group.setChecked(True);w.update_geometry()
    assert e.get_parameters().analysis_le_mm==.5
    e.analysis_controls['analysis_le_mm'].setValue(1.);w.update_geometry()
    assert w.impeller_geometry.analysis_shroud is not None
    np.testing.assert_array_equal(w.impeller_geometry.sections[-1].master_ps.xyz,tip)
    assert 'analysis_shroud' in w.model_preview_3d.surfaces
    assert w.meridional_editor.context.analysis_profiles
    for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)
    p=deepcopy(w.get_parameters());path=tmp_path/'analysis.json'
    w.save_to_path(path);w.load_from_path(path);assert w.get_parameters()==p
    e=w.tip_clearance_editor;e.analysis_group.setChecked(False);w.update_geometry()
    assert w.impeller_geometry.analysis_shroud is None
    assert 'analysis_shroud' not in w.model_preview_3d.surfaces
    assert not w.meridional_editor.context.analysis_profiles
    w.undo();assert w.get_parameters()==p
    w.redo();assert w.get_parameters().tip_clearance==baseline.tip_clearance


def test_per_row_independence_all_rows_and_delayed_input(window):
    w=window;e=enable(w);e.analysis_group.setChecked(True);w.update_geometry()
    box=e.analysis_controls['analysis_te_mm'];box.setFocus();box.lineEdit().selectAll()
    count=w.undo_stack.count();QTest.keyClicks(box.lineEdit(),'1.25')
    assert w.get_parameters().tip_clearance.analysis_te_mm==.5 and w.undo_stack.count()==count
    QTest.keyClick(box,Qt.Key.Key_Return);w.update_geometry()
    assert w.get_parameters().tip_clearance.analysis_te_mm==1.25
    w.add_blade_row('impeller','Second');second=w._active_row
    e.analysis_controls['analysis_te_mm'].setValue(2.);w.update_geometry()
    w.select_blade_row('row-1');assert w.get_parameters().tip_clearance.analysis_te_mm==1.25
    w.select_blade_row(second);assert w.get_parameters().tip_clearance.analysis_te_mm==2.
    w._select_meridional()
    assert len(w.meridional_editor.context.analysis_profiles)==2
    assert 'analysis_shroud' in w.model_preview_3d.surfaces


def test_coordinate_dialog_offers_shroud_sources():
    app=QApplication.instance() or QApplication([]);d=CoordinateExportDialog()
    try:
        assert d.options().shroud_source=='drawing'
        d.shroud_source.setCurrentIndex(2);assert d.options().shroud_source=='both'
        d.shroud_source.setCurrentIndex(1);assert d.options().shroud_source=='analysis'
    finally:
        d.close();d.deleteLater();app.processEvents()
