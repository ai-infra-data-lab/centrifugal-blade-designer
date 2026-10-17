"""Per-row controls, delayed editing, Tip/casing display, history and JSON."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import TipClearanceParameters


def dispose(w,app):
    for dialog in w._tool_dialogs.values():dialog.close()
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_controls_commit_on_focus_and_preserve_undo_and_json(tmp_path):
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        before=deepcopy(w.get_parameters());hub=deepcopy(w.impeller_geometry.sections[0].master_ps.xyz)
        editor=w.tip_clearance_editor
        editor.setChecked(True)
        baseline=deepcopy(w.get_parameters())
        box=editor.controls['le_mm'];box.lineEdit().selectAll()
        QTest.keyClicks(box.lineEdit(),'0.5')
        assert w.get_parameters().tip_clearance.le_mm==0
        box.interpretText();box.editingFinished.emit();w.update_geometry()
        assert w.get_parameters().tip_clearance.le_mm==.5
        np.testing.assert_array_equal(w.impeller_geometry.sections[0].master_ps.xyz,hub)
        assert w.impeller_geometry.tip is not None
        assert 'tip_wall' in w.model_preview_3d.surfaces
        assert not w.model_preview_3d.visibility_controls['tip_wall'].isHidden()
        assert w.model_preview_3d.visibility_controls['shroud'].text()=='Casing'
        assert w.meridional_editor.context.tip_profiles
        w.undo();assert w.get_parameters()==baseline
        w.redo();assert w.get_parameters().tip_clearance.le_mm==.5
        path=tmp_path/'clearance.json';w.save_to_path(path);w.load_from_path(path)
        assert w.get_parameters().tip_clearance==TipClearanceParameters(.5,0.)
        assert w.impeller_geometry.tip is not None
        editor.setChecked(False);w.update_geometry()
        assert w.get_parameters().tip_clearance is None and w.impeller_geometry.tip is None
        assert 'tip_wall' not in w.model_preview_3d.surfaces
        assert not w.meridional_editor.context.tip_profiles
        assert before.shroud==w.get_parameters().shroud
    finally:dispose(w,app)


def test_each_impeller_has_independent_clearance_and_all_rows_show_in_meridional(tmp_path):
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        w.select_blade_row('row-1')
        w.tip_clearance_editor.setChecked(True)
        w.tip_clearance_editor.controls['le_mm'].setValue(.5);w.update_geometry()
        first=w._active_row
        w.add_blade_row('impeller','Second Rotor')
        second=w._active_row
        w.tip_clearance_editor.controls['le_mm'].setValue(.2);w.update_geometry()
        assert w.get_parameters().tip_clearance.le_mm==.2
        w.select_blade_row(first)
        assert w.get_parameters().tip_clearance.le_mm==.5
        w.select_blade_row('row-2')
        assert w._selected_3d_geometry.tip is None
        assert w.tip_clearance_editor.isHidden()
        assert 'tip_wall' not in w.model_preview_3d.surfaces
        w.rename_blade_row(second,'Impeller')
        w._select_meridional()
        assert len(w.meridional_editor.context.tip_profiles)==2
        assert all('Impeller [' in name for name in w.meridional_editor.context.tip_profiles)
        assert 'tip_wall' in w.model_preview_3d.surfaces
        w.select_blade_row(second)
        assert w.get_parameters().tip_clearance.le_mm==.2
        path=tmp_path/'rows.json';w.save_to_path(path);w.load_from_path(path)
        values={r.identifier:r.parameters.tip_clearance for r in w.get_parameters().blade_rows}
        assert values[first].le_mm==.5 and values[second].le_mm==.2
    finally:dispose(w,app)


def test_loaded_precision_and_invalid_width_do_not_use_old_passage_result():
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        p=w.get_parameters();p.tip_clearance=TipClearanceParameters(.123456789012345,.234567890123456)
        w.set_parameters(p);w.update_geometry()
        assert w.get_parameters().tip_clearance==p.tip_clearance
        w.tip_clearance_editor.controls['te_mm'].setValue(100.)
        w.update_geometry()
        assert 'ERROR' in w.messages.toPlainText()
        assert w.passage_widget.source is None
        assert w.get_parameters().tip_clearance.te_mm==100.
    finally:dispose(w,app)
