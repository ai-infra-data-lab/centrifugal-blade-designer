"""Downstream choice participates in the normal row/history/save workflow."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from test_tip_clearance_gui import dispose


def test_downstream_choice_undo_rows_and_json(tmp_path):
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        w.select_blade_row('row-1');editor=w.trim_editor
        editor.setChecked(True)
        editor.controls['shroud_area_cut_percent'].setValue(5);w.update_geometry()
        assert w.get_parameters().impeller_trim.shroud_downstream_mode=='cut'
        editor.downstream.setCurrentIndex(editor.downstream.findData('restore'));w.update_geometry()
        assert w.get_parameters().impeller_trim.shroud_downstream_mode=='restore'
        assert w._selected_3d_geometry is w.impeller_geometry
        assert w.passage_widget.source[0] is w.impeller_geometry
        w.undo();assert w.get_parameters().impeller_trim.shroud_downstream_mode=='cut'
        w.redo();assert w.get_parameters().impeller_trim.shroud_downstream_mode=='restore'
        w.select_blade_row('row-2');w.select_blade_row('row-1')
        assert editor.downstream.currentData()=='restore'
        path=tmp_path/'restored.json';w.save_to_path(path);w.load_from_path(path)
        assert editor.downstream.currentData()=='restore'
        assert w.get_parameters().impeller_trim.shroud_downstream_mode=='restore'
    finally:dispose(w,app)
