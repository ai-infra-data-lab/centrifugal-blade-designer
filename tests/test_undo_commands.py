import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF,Qt,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import RotationDirection

@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();QTest.qWait(30)
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()

@pytest.mark.parametrize("edit",["angle","thickness","le","te","start","segment","station","edge_position","output","rotation","copy","span","add_point","delete_point","add_segment","delete_segment","move_segment","invalid"])
def test_project_undo_redo_operations(window,edit):
    w=window
    if edit=="copy":
        w.select_section(1);w.angle_editor.table.cellWidget(1,1).setValue(40);w.commit_edit()
    if edit=="delete_point":w.angle_editor.add_point()
    if edit in ("delete_segment","move_segment"):w.meridional_editor.table.selectRow(1)
    before=deepcopy(w.get_parameters());count=w.undo_stack.count()
    if edit=="angle":w.angle_editor.table.cellWidget(1,1).setValue(48)
    if edit=="thickness":w.thickness_editor.table.cellWidget(1,1).setValue(5)
    if edit=="le":w.panel.controls["le_type"].setCurrentIndex(1)
    if edit=="te":w.panel.controls["te_type"].setCurrentIndex(2)
    if edit=="start":w.meridional_editor.start_controls["start_z"].setValue(3)
    if edit=="segment":w.meridional_editor.table.cellWidget(2,1).setValue(65)
    if edit=="station":w.meridional_editor.station_table.cellWidget(1,1).setValue(.18)
    if edit=="edge_position":w.meridional_editor.blade_edges.controls["impeller_edges","leading_edge","hub"].setValue(.2)
    if edit=="output":w.panel.controls["ps_points"].setValue(51)
    if edit=="rotation":w.reverse_rotation()
    if edit=="copy":w.copy_section(True)
    if edit=="span":w.add_span_section(.5)
    if edit=="add_point":w.angle_editor.add_point()
    if edit=="delete_point":w.angle_editor.delete_point()
    if edit=="add_segment":w.meridional_editor.add_segment(False)
    if edit=="delete_segment":w.meridional_editor.delete_segment()
    if edit=="move_segment":w.meridional_editor.move_segment(1)
    if edit=="invalid":w.meridional_editor.blade_edges.controls["impeller_edges","leading_edge","hub"].setValue(.9)
    w.commit_edit();after=deepcopy(w.get_parameters())
    assert w.undo_stack.count()==count+1
    assert after!=before
    w.undo();assert w.get_parameters()==before
    w.redo();assert w.get_parameters()==after

def test_numeric_steps_group_and_new_open_save_history(window,tmp_path):
    w=window;box=w.angle_editor.table.cellWidget(1,1)
    for val in (60,58,55):box.setValue(val)
    assert w.undo_stack.count()==0
    box.editingFinished.emit();assert w.undo_stack.count()==1
    w.save_to_path(tmp_path/"project.json");assert w.undo_stack.count()==1
    w.new_project();assert w.undo_stack.count()==0
    w.reverse_rotation();w.load_from_path(tmp_path/"project.json");assert w.undo_stack.count()==0
    assert w.angle_editor.get_points()[1].value==55

def drag(w,plot,start,finish):
    app=QApplication.instance();viewport=plot.viewport()
    QTest.mouseMove(viewport,start);QTest.qWait(30)
    QTest.mousePress(viewport,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
    for step in range(1,6):
        pos=start+(finish-start)*step/5
        event=QMouseEvent(QEvent.Type.MouseMove,QPointF(pos),QPointF(viewport.mapToGlobal(pos)),
            Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        app.sendEvent(viewport,event);app.processEvents();QTest.qWait(20)
    QTest.mouseRelease(viewport,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,finish);QTest.qWait(250)

@pytest.mark.parametrize("kind",["angle","thickness","blade_edge"])
def test_real_drag_is_one_undo_command(window,kind):
    w=window
    if kind=="blade_edge":
        w._select_meridional();plot=w.meridional_editor.plot
        w.tabs.currentWidget().ensureWidgetVisible(w.meridional_editor.context)
        item=w.meridional_editor.context.edge_handles[0];pos=item.pos[0].copy();target=pos+np.array([4.,2.])
    else:
        w.tabs.setCurrentIndex(0 if kind=="angle" else 1)
        editor=w.angle_editor if kind=="angle" else w.thickness_editor;plot=editor.plot
        point=editor.get_points()[1];pos=np.array([point.m_blade_norm,point.value]);target=pos+[.15,1.]
    QTest.qWait(100)
    def screen(p):return plot.mapFromScene(plot.getViewBox().mapViewToScene(QPointF(*p)))
    before=deepcopy(w.get_parameters());count=w.undo_stack.count()
    drag(w,plot,screen(pos),screen(target))
    after=deepcopy(w.get_parameters())
    assert after!=before;assert w.undo_stack.count()==count+1
    w.undo();assert w.get_parameters()==before
    w.redo();assert w.get_parameters()==after

def test_undo_retains_ranges_and_camera(window):
    w=window;view=w.blade_plot.getViewBox()
    view.setRange(xRange=(90,110),yRange=(5,25),padding=0)
    ranges=np.array(view.viewRange())
    w.preview_3d.camera_position["azimuth"]=83;camera=deepcopy(w.preview_3d.camera_position)
    w.reverse_rotation();w.update_geometry();w.undo();w.redo();w.update_geometry()
    np.testing.assert_allclose(view.viewRange(),ranges)
    for key,value in camera.items():np.testing.assert_allclose(w.preview_3d.camera_position[key],value)
    assert w.get_parameters().rotation_direction is RotationDirection.CW

def test_global_shortcuts_inside_numeric_editor(window):
    w=window;box=w.angle_editor.table.cellWidget(1,1)
    box.setValue(51);box.editingFinished.emit()
    box.setFocus();QTest.keyClick(box.lineEdit(),Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
    assert w.angle_editor.get_points()[1].value==62
    box=w.angle_editor.table.cellWidget(1,1);box.setFocus()
    QTest.keyClick(box.lineEdit(),Qt.Key.Key_Y,Qt.KeyboardModifier.ControlModifier)
    assert w.angle_editor.get_points()[1].value==51
    box=w.angle_editor.table.cellWidget(1,1);box.setFocus()
    QTest.keyClick(box.lineEdit(),Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
    box=w.angle_editor.table.cellWidget(1,1);box.setFocus()
    QTest.keyClick(box.lineEdit(),Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    assert w.angle_editor.get_points()[1].value==51

def test_all_endpoint_rows_walls_and_edges_are_undoable(window):
    w=window
    for key in ("impeller_edges","diffuser_edges"):
        for side in ("leading_edge","trailing_edge"):
            for wall in ("hub","shroud"):
                before=deepcopy(w.get_parameters());count=w.undo_stack.count()
                box=w.meridional_editor.blade_edges.controls[key,side,wall]
                box.setValue(box.value()+.003);box.editingFinished.emit()
                after=deepcopy(w.get_parameters());assert after!=before
                assert w.undo_stack.index()==count+1
                w.undo();assert w.get_parameters()==before
                w.redo();assert w.get_parameters()==after

def test_shroud_thickness_and_span_delete_history(window):
    w=window
    w.meridional_editor.selector.setCurrentIndex(1)
    before=deepcopy(w.get_parameters())
    box=w.meridional_editor.table.cellWidget(2,1);box.setValue(65);box.editingFinished.emit()
    assert w.get_parameters().shroud!=before.shroud
    w.undo();assert w.get_parameters()==before
    w.thickness_editor.add_point();after=deepcopy(w.get_parameters())
    w.thickness_editor.delete_point();w.undo();assert w.get_parameters()==after
    w.add_span_section(.5);after=deepcopy(w.get_parameters())
    w.delete_span_section();w.undo();assert w.get_parameters()==after
    assert w.undo_stack.undoLimit()==200

def test_reparented_edge_and_output_controls_commit_on_edit_finished(window):
    w=window
    for side in ("le","te"):
        count=w.undo_stack.count()
        w.panel.controls[side+"_type"].setCurrentIndex(1)
        assert w.undo_stack.count()==count+1
        count=w.undo_stack.count()
        box=w.panel.controls[side+"_ellipse_ratio"];box.setValue(1.7);box.editingFinished.emit()
        assert w.undo_stack.count()==count+1
    for box,value in ((w.panel.controls["ps_points"],51),(w.panel.export_settings.digits,7)):
        count=w.undo_stack.count();box.setValue(value);box.editingFinished.emit()
        assert w.undo_stack.count()==count+1
    count=w.undo_stack.count()
    box=w.output_editor.controls["profile_curve_filename"]
    box.setText("new_profile.curve");box.editingFinished.emit()
    assert w.undo_stack.count()==count+1
    w.undo();assert w.get_parameters().turbogrid.profile_curve_filename=="profile.curve"

def test_visible_row_boundaries_follow_independent_tilted_edges(window):
    from blade_designer.models.blade_edge import BladeEdgePosition
    from blade_designer.models.flow_path import StationType
    from blade_designer.geometry.blade_edge import edge_endpoints
    w=window;p=w.get_parameters();stations=deepcopy(p.flow_path)
    p.impeller_edges.leading_edge=BladeEdgePosition(.2,.28)
    p.impeller_edges.trailing_edge=BladeEdgePosition(.72,.82)
    w.set_parameters(p);w.update_geometry()
    assert w.get_parameters().flow_path==stations
    for context in (w.context_meridional,w.meridional_editor.context):
        for side,kind in (("leading_edge",StationType.IMP_LE),("trailing_edge",StationType.IMP_TE)):
            line=context.boundaries[list(StationType).index(kind)]
            np.testing.assert_allclose(np.column_stack(line.getData()),
                edge_endpoints(getattr(p.impeller_edges,side),w.impeller_geometry.hub,w.impeller_geometry.shroud))
