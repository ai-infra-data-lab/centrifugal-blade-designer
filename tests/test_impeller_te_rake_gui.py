import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.geometry.impeller_parameter_mapper import measure_te_rake
from blade_designer.models.blade_rows import initial_rows
from test_impeller_te_rake import radial_parameters


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([]);w=MainWindow();w.show();app.processEvents()
    w.set_parameters(radial_parameters());w.update_geometry();w._reset_history()
    index=next(i for i in range(w.tabs.count()) if w.tabs.tabText(i)=='LE / TE')
    w.tabs.setCurrentIndex(index)
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_target_undo_redo_json_and_preview_preserve_beta(window,tmp_path):
    w=window;beta=deepcopy([s.blade_angle for s in w.get_parameters().sections])
    original=w.impeller_geometry.sections[-1].camber.xyz.copy()
    w.te_rake.setValue(20);w.rake_group.setChecked(True);w.update_geometry()
    assert w.get_parameters().impeller_te_rake_deg==20
    assert measure_te_rake(w.impeller_geometry)==pytest.approx(20,abs=1e-8)
    assert [s.blade_angle for s in w.get_parameters().sections]==beta
    assert 'Actual: 20' in w.te_rake_status.text()
    for v in (w.preview_3d,w.model_preview_3d):
        np.testing.assert_array_equal(v.base_lines['Tip camber'][0],w.impeller_geometry.sections[-1].camber.xyz)
    w.undo();assert not w.rake_group.isChecked()
    np.testing.assert_array_equal(w.impeller_geometry.sections[-1].camber.xyz,original)
    w.redo();assert w.rake_group.isChecked()
    path=tmp_path/'rake.json';w.save_to_path(path);w.new_project();w.load_from_path(path)
    assert w.rake_group.isChecked() and w.te_rake.value()==20
    assert measure_te_rake(w.impeller_geometry)==pytest.approx(20,abs=1e-8)


def test_keyboard_waits_for_confirmation_and_undo_works_inside_rake(window):
    w=window;w.rake_group.setChecked(True);w.update_geometry();before=w.undo_stack.count()
    box=w.te_rake;box.setFocus();box.lineEdit().selectAll()
    QTest.keyClicks(box.lineEdit(),'15')
    assert box.value()==0 and w.get_parameters().impeller_te_rake_deg==0
    assert w.undo_stack.count()==before
    QTest.keyClick(box,Qt.Key.Key_Return);w.update_geometry()
    assert w.get_parameters().impeller_te_rake_deg==15
    assert w.undo_stack.count()==before+1
    QTest.keyClick(box,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
    assert w.te_rake.value()==0 and w.rake_group.isChecked()


def test_independent_impeller_targets_and_stator_visibility(window):
    w=window;p=w.get_parameters();p.blade_rows=initial_rows(p)
    p.active_blade_row='row-1';w.set_parameters(p);w._reset_history();w.update_geometry()
    w.te_rake.setValue(10);w.rake_group.setChecked(True);w.update_geometry()
    w.add_blade_row('impeller','Second Impeller')
    second=w.get_parameters().active_blade_row
    w.te_rake.setValue(-15);w.rake_group.setChecked(True);w.update_geometry()
    w.select_blade_row('row-1');assert w.te_rake.value()==10
    w.select_blade_row(second);assert w.te_rake.value()==-15
    w.select_blade_row('row-2');assert w.rake_group.isHidden()
    w.select_blade_row('row-1');assert not w.rake_group.isHidden()
    assert w.get_parameters().impeller_te_rake_deg==10


def test_unreachable_edit_retains_last_valid_shape_and_undo(window):
    w=window;w.te_rake.setValue(20);w.rake_group.setChecked(True);w.update_geometry()
    previous=w.impeller_geometry
    w.te_rake.setValue(89);w.update_geometry()
    assert w.impeller_geometry is previous
    assert 'unreachable' in w.messages.toPlainText()
    w.undo();assert w.te_rake.value()==20
    assert measure_te_rake(w.impeller_geometry)==pytest.approx(20,abs=1e-8)


def test_load_without_edit_preserves_full_precision_target(window,tmp_path):
    w=window;p=w.get_parameters();p.impeller_te_rake_deg=12.345678901234567
    w.set_parameters(p);w.update_geometry()
    assert w.get_parameters().impeller_te_rake_deg==p.impeller_te_rake_deg
    path=tmp_path/'precision.json';w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters().impeller_te_rake_deg==p.impeller_te_rake_deg
