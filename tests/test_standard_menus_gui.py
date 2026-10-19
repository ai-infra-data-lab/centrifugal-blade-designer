import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QToolBar,QFileDialog
from blade_designer.gui.main_window import MainWindow


def dispose(w,app):
    for other in w._optimization_windows:dispose(other,app)
    for dialog in w._tool_dialogs.values():dialog.close()
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


@pytest.mark.parametrize('mode',['design','optimization'])
def test_standard_menu_order_and_no_toolbar(mode):
    app=QApplication.instance() or QApplication([]);w=MainWindow(mode=mode)
    try:
        assert [a.text() for a in w.menuBar().actions()]==['File','Edit','View','Tools','About']
        assert [a.text() for a in w.file_menu.actions() if not a.isSeparator()]==[
            'New','Open Project','Save Project','Export','Exit']
        exports=next(a.menu() for a in w.file_menu.actions() if a.text()=='Export')
        assert [a.text() for a in exports.actions()]==[
            'Diffuser Segments CSV','Diffuser Contour CSV','TurboGrid Export','Export Readiness','Selected Row XYZ CSV','Selected Row Coordinate CSV / TXT']
        assert w.findChildren(QToolBar)==[]
        assert all(action in w.file_menu.actions() for action in w.project_actions.values())
        assert w.undo_action in w.edit_menu.actions() and w.redo_action in w.edit_menu.actions()
        for shortcut in ('Ctrl+N','Ctrl+O','Ctrl+S','Ctrl+Z'):
            actions=[a for a in w.findChildren(QAction) if any(s.toString()==shortcut for s in a.shortcuts())]
            assert len(actions)==1
    finally:dispose(w,app)


def test_each_export_menu_dispatches_once(monkeypatch):
    calls=[]
    for method in ('export_segments_dialog','export_contour_dialog','export_turbogrid_dialog','show_export_readiness','export_row_xyz_dialog','export_coordinate_dialog'):
        monkeypatch.setattr(MainWindow,method,lambda self,checked=False,method=method:calls.append(method))
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        menu=next(a.menu() for a in w.file_menu.actions() if a.text()=='Export')
        for action in menu.actions():action.trigger()
        assert calls==['export_segments_dialog','export_contour_dialog','export_turbogrid_dialog','show_export_readiness','export_row_xyz_dialog','export_coordinate_dialog']
    finally:dispose(w,app)


def test_save_shortcut_and_menu_open_one_dialog_each(monkeypatch):
    calls=[]
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(calls.append('save') or ('','')))
    app=QApplication.instance() or QApplication([]);w=MainWindow();w.show();w.activateWindow();QTest.qWait(40)
    try:
        QTest.keyClick(w,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
        assert calls==['save']
        w.project_actions['Save Project'].trigger()
        assert calls==['save','save']
    finally:dispose(w,app)


def test_rotation_menu_syncs_reverse_undo_and_load(tmp_path):
    from blade_designer.models.parameters import RotationDirection
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        w.rotation_actions['CW'].trigger();w.commit_edit();w.update_geometry()
        assert w.get_parameters().rotation_direction==RotationDirection.CW
        assert w.rotation_actions['CW'].isChecked() and not w.rotation_actions['CCW'].isChecked()
        w.undo()
        assert w.rotation_actions['CCW'].isChecked()
        w.redo();assert w.rotation_actions['CW'].isChecked()
        next(a for a in w.edit_menu.actions() if a.text()=='Reverse Rotation').trigger()
        w.commit_edit();assert w.rotation_actions['CCW'].isChecked()
        w.rotation_cw.setChecked(True);w.commit_edit()
        assert w.rotation_actions['CW'].isChecked()
        path=tmp_path/'rotation.json';w.save_to_path(path);w.new_project();w.load_from_path(path)
        assert w.rotation_actions['CW'].isChecked()
    finally:dispose(w,app)


def test_projection_menu_syncs_target_and_existing_controls():
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        w.projection_actions['XZ'].trigger()
        assert w.projection.currentText()=='XZ' and w.projection_actions['XZ'].isChecked()
        w.projection.setCurrentText('YZ')
        assert w.projection_actions['YZ'].isChecked()
        w.select_blade_row('row-2')
        assert not w.projection_menu.isEnabled() and w.projection_actions['XY'].isChecked()
        w.select_blade_row('row-1')
        assert w.projection_menu.isEnabled() and w.projection_actions['YZ'].isChecked()
    finally:dispose(w,app)


def test_tools_opens_independent_optimization_window():
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        action=w.tools_menu.actions()[0]
        assert action.text()=='Open Optimization Mode in Separate Window'
        action.trigger()
        assert len(w._optimization_windows)==1
        other=w._optimization_windows[0]
        assert other.isVisible() and other.mode=='optimization' and w.mode=='design'
    finally:dispose(w,app)
