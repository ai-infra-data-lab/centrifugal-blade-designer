"""Independent settings, source editing, central views, history and persistence."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow
from test_tip_clearance_gui import dispose


def test_focus_commit_undo_roundtrip_and_source_editors(tmp_path):
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        w.select_blade_row('row-1');source=deepcopy(w.get_parameters())
        editor=w.trim_editor;editor.setChecked(True)
        enabled=deepcopy(w.get_parameters());box=editor.controls['shroud_area_cut_percent']
        box.lineEdit().selectAll();QTest.keyClicks(box.lineEdit(),'10')
        assert w.get_parameters().impeller_trim.shroud_area_cut_percent==0
        box.interpretText();box.editingFinished.emit();w.update_geometry()
        p=w.get_parameters();assert p.impeller_trim.shroud_area_cut_percent==10
        assert p.sections==source.sections and p.hub==source.hub and p.shroud==source.shroud
        g=w.impeller_geometry
        assert w._selected_3d_geometry is g
        assert w.passage_widget.source[0] is g
        np.testing.assert_array_equal(w.context_meridional.curves[1].getData()[1],g.source_geometry.shroud.r)
        assert w.meridional_editor.context.trim_profiles
        assert '面積比: 0.9' in editor.status.text()
        w.undo();assert w.get_parameters()==enabled
        w.redo();assert w.get_parameters().impeller_trim.shroud_area_cut_percent==10
        path=tmp_path/'trim.json';w.save_to_path(path);w.load_from_path(path)
        assert w.get_parameters().impeller_trim.shroud_area_cut_percent==10
        editor.setChecked(False);w.update_geometry()
        assert w.impeller_geometry.source_geometry is None
        assert not w.meridional_editor.context.trim_profiles
    finally:dispose(w,app)


def test_rows_meridional_preview_and_invalid_current_input(tmp_path):
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        w.select_blade_row('row-1');w.trim_editor.setChecked(True)
        w.trim_editor.controls['shroud_area_cut_percent'].setValue(8);w.update_geometry()
        first=w._active_row
        w.add_blade_row('impeller','Trim B');second=w._active_row
        w.trim_editor.controls['shroud_area_cut_percent'].setValue(12);w.update_geometry()
        w.select_blade_row(first)
        assert w.get_parameters().impeller_trim.shroud_area_cut_percent==8
        w.select_blade_row('row-2');assert w.trim_editor.isHidden()
        assert w._selected_3d_geometry.source_geometry is None
        w._select_meridional();assert len(w.meridional_editor.context.trim_profiles)==2
        w.select_blade_row(second)
        assert w.get_parameters().impeller_trim.shroud_area_cut_percent==12
        valid=w.impeller_geometry
        w.trim_editor.mode.setCurrentIndex(w.trim_editor.mode.findData('diameter'))
        w.trim_editor.controls['diameter_mm'].setValue(.1);w.update_geometry()
        assert w.passage_widget.source is None
        assert w.impeller_geometry is valid
        assert 'ERROR' in w.messages.toPlainText()
        assert not (tmp_path/'missing').exists()
    finally:dispose(w,app)
