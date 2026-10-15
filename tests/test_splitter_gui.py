import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import SplitterParameters
from blade_designer.models.blade_rows import initial_rows
from test_impeller_te_rake import radial_parameters


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([]);w=MainWindow();w.show();app.processEvents()
    w.set_parameters(radial_parameters());w.update_geometry();w._reset_history()
    w.tabs.setCurrentIndex(next(i for i in range(w.tabs.count()) if w.tabs.tabText(i)=='Splitter'))
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_enable_edit_undo_json_and_both_previews(window,tmp_path):
    w=window;e=w.splitter_editor;baseline=w.impeller_geometry.sections[0].ps.xyz.copy()
    e.setChecked(True);w.update_geometry()
    assert w.get_parameters().splitter==SplitterParameters()
    np.testing.assert_array_equal(w.impeller_geometry.sections[0].ps.xyz,baseline)
    for v in (w.preview_3d,w.model_preview_3d):
        np.testing.assert_array_equal(v.base_lines['Splitter Hub camber'][0],w.impeller_geometry.splitter_sections[0].camber.xyz)
    x,y=w.blade_plot.splitter_curves['PS'].getData()
    np.testing.assert_array_equal(x[:-1],w.impeller_geometry.splitter_sections[0].master_ps.x)
    e.controls['pitch_fraction'].setValue(35);w.update_geometry()
    assert w.get_parameters().splitter.pitch_fraction==.35
    w.undo();assert e.controls['pitch_fraction'].value()==50
    w.undo();assert w.get_parameters().splitter is None and w.impeller_geometry.splitter_sections is None
    assert not any(name.startswith('Splitter ') for name in w.model_preview_3d.base_lines)
    w.redo();path=tmp_path/'project.json';w.save_to_path(path);w.new_project();w.load_from_path(path)
    assert w.get_parameters().splitter==SplitterParameters() and w.impeller_geometry.splitter_sections


def test_keyboard_confirmation_and_annulus_counts(window):
    w=window;e=w.splitter_editor;e.setChecked(True);w.update_geometry()
    box=e.controls['hub_start_fraction'];box.setFocus();box.lineEdit().selectAll();before=w.undo_stack.count()
    QTest.keyClicks(box.lineEdit(),'65')
    assert w.get_parameters().splitter.hub_start_fraction==.5 and w.undo_stack.count()==before
    QTest.keyClick(box,Qt.Key.Key_Return);w.update_geometry()
    assert w.get_parameters().splitter.hub_start_fraction==.65 and w.undo_stack.count()==before+1
    camera=deepcopy(w.model_preview_3d.camera_position)
    w.annulus_2d.setChecked(True);w.annulus_3d.setChecked(True)
    n=w.get_parameters().geometry.vane_count
    assert len(w.model_preview_3d.lines)==len(w.model_preview_3d.base_lines)*n
    x,y=w.annulus_plot.splitter_curves['PS'].getData();assert np.count_nonzero(np.isnan(x))==n
    for k,v in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[k],v)
    w.select_section(2);w.update_geometry()
    np.testing.assert_array_equal(w.blade_plot.splitter_curves['PS'].getData()[0][:-1],w.impeller_geometry.splitter_sections[2].master_ps.x)


def test_independent_rows_static_visibility_all_rows_and_loaded_precision(window,tmp_path):
    w=window;p=w.get_parameters();p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
    w.set_parameters(p);w.update_geometry();w._reset_history();w.splitter_editor.setChecked(True);w.update_geometry()
    w.add_blade_row('impeller','Second');second=w.get_parameters().active_blade_row
    w.splitter_editor.setChecked(True);w.splitter_editor.controls['tip_start_fraction'].setValue(70);w.update_geometry()
    w.select_blade_row('row-1');assert w.get_parameters().splitter.tip_start_fraction==.5
    w.select_blade_row(second);assert w.get_parameters().splitter.tip_start_fraction==.7
    w.select_blade_row('row-2');assert w.splitter_editor.isHidden()
    assert not any(k.startswith('Splitter ') for k in w.model_preview_3d.base_lines)
    w._select_meridional();assert any('Splitter ' in k for k in w.model_preview_3d.base_lines)
    w.select_blade_row('row-1');p=w.get_parameters();p.splitter.pitch_fraction=.345678901234567
    w.set_parameters(p);w.update_geometry();assert w.get_parameters().splitter.pitch_fraction==p.splitter.pitch_fraction
    path=tmp_path/'rows.json';w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters().splitter.pitch_fraction==p.splitter.pitch_fraction


def test_independent_copy_angle_thickness_edit_undo_and_save(window,tmp_path):
    w=window;e=w.splitter_editor;e.setChecked(True);w.update_geometry()
    main=w.impeller_geometry.sections[0].ps.xyz.copy();linked=w.impeller_geometry.splitter_sections[0].ps.xyz.copy()
    e.independent.setChecked(True);w.update_geometry()
    np.testing.assert_array_equal(w.impeller_geometry.splitter_sections[0].ps.xyz,linked)
    e.angle_editor.series[0].move_point(1,1,12);w.update_geometry()
    assert w.get_parameters().splitter.sections[0].blade_angle.points[1].value==12
    assert not np.allclose(w.impeller_geometry.splitter_sections[0].ps.xyz,linked)
    np.testing.assert_array_equal(w.impeller_geometry.sections[0].ps.xyz,main)
    e.thickness_editor.series[1].move_point(1,.35,2.5);w.update_geometry()
    assert w.get_parameters().splitter.sections[-1].thickness.points[1].value==2.5
    path=tmp_path/'independent.json';w.save_to_path(path);before=deepcopy(w.get_parameters())
    w.new_project();w.load_from_path(path);assert w.get_parameters()==before
    e=w.splitter_editor;e.copy_button.click();w.update_geometry()
    np.testing.assert_array_equal(w.impeller_geometry.splitter_sections[0].ps.xyz,linked)
    w.undo();assert w.get_parameters()==before
    e.independent.setChecked(False);w.update_geometry()
    assert w.get_parameters().splitter.sections is None
    np.testing.assert_array_equal(w.impeller_geometry.splitter_sections[0].ps.xyz,linked)


def test_independent_mode_undo_and_keyboard(window):
    w=window;e=w.splitter_editor;e.setChecked(True);w.update_geometry();e.independent.setChecked(True);w.update_geometry()
    before=deepcopy(w.get_parameters());count=w.undo_stack.count()
    editor=e.angle_editor.series[0];box=editor.table.cellWidget(1,1)
    box.setFocus();box.lineEdit().selectAll();QTest.keyClicks(box.lineEdit(),'18')
    assert w.get_parameters()==before
    QTest.keyClick(box,Qt.Key.Key_Return);w.update_geometry()
    assert w.get_parameters().splitter.sections[0].blade_angle.points[1].value==18
    assert w.undo_stack.count()==count+1
    QTest.keyClick(box,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
    assert w.get_parameters()==before
    w.undo();assert not e.independent.isChecked() and w.get_parameters().splitter.sections is None
