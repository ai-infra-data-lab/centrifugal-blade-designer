import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from blade_designer.gui.blade_edge_editor import BladeEdgeEditor
from blade_designer.gui.main_window import MainWindow
from blade_designer.gui.meridional_editor import MeridionalEditor
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.meridional_segments import generate_meridional,sample_meridional
from blade_designer.fileio.project_io import load_project
from blade_designer.geometry.blade_edge import edge_endpoints,rescale_extended_wall_edges


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def physical_edges(p):
    walls=[generate_meridional(getattr(p,wall)) for wall in ("hub","shroud")]
    return np.array([edge_endpoints(getattr(getattr(p,key),side),*walls)
                     for key in ("impeller_edges","diffuser_edges")
                     for side in ("leading_edge","trailing_edge")])


@pytest.mark.parametrize("field,row,column,text",[
    ("length",2,1,"65"),("radius",1,2,"31"),("sweep_deg",1,3,"85"),
    ("start_z",None,None,"3"),("start_r",None,None,"52"),
    ("start_angle_deg",None,None,"1"),
])
def test_wall_numeric_typing_waits_for_focus_loss(app,field,row,column,text):
    editor=MeridionalEditor();editor.show();app.processEvents()
    try:
        box=editor.start_controls[field] if row is None else editor.table.cellWidget(row,column)
        before=editor.get_curves();changes=[]
        editor.parametersChanged.connect(lambda:changes.append(editor.get_curves()))
        box.setFocus();box.selectAll();app.processEvents()
        for digit in text:
            QTest.keyClicks(box,digit);app.processEvents()
            assert editor.get_curves()==before and changes==[]
        editor.selector.setFocus();app.processEvents()
        assert len(changes)==1
        curve=editor.get_curves()[0]
        assert getattr(curve if row is None else curve.segments[row],field)==float(text)
        # Leaving an unchanged field must not schedule another recalculation.
        box.setFocus();app.processEvents();editor.selector.setFocus();app.processEvents()
        assert len(changes)==1
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_wall_numeric_enter_commits_once(app):
    editor=MeridionalEditor();editor.show();app.processEvents()
    try:
        box=editor.table.cellWidget(2,1);changes=[]
        editor.parametersChanged.connect(lambda:changes.append(editor.get_curves()))
        box.setFocus();box.selectAll();QTest.keyClicks(box,"65");app.processEvents()
        assert changes==[]
        QTest.keyClick(box,Qt.Key.Key_Return);app.processEvents()
        assert len(changes)==1 and editor.get_curves()[0].segments[2].length==65
        editor.selector.setFocus();app.processEvents();assert len(changes)==1
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_wall_numeric_focus_commit_is_one_undo(app):
    w=MainWindow();w.show();app.processEvents()
    try:
        w.navigator.tree.setCurrentItem(w.navigator.meridional_item);app.processEvents()
        box=w.meridional_editor.table.cellWidget(2,1)
        before=deepcopy(w.get_parameters());count=w.undo_stack.count()
        box.setFocus();box.selectAll();QTest.keyClicks(box,"65");app.processEvents()
        assert w.get_parameters()==before and w.undo_stack.count()==count
        w.meridional_editor.selector.setFocus();app.processEvents()
        after=deepcopy(w.get_parameters())
        assert after.hub.segments[2].length==65 and w.undo_stack.count()==count+1
        w.undo();assert w.get_parameters()==before
        w.redo();assert w.get_parameters()==after
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()


@pytest.mark.parametrize("wall_index",[0,1])
@pytest.mark.parametrize("field,value",[("length",65),("radius",22),("sweep_deg",40),("clockwise",True)])
def test_tail_dimension_edit_preserves_physical_edges_and_pending(app,wall_index,field,value):
    editor=MeridionalEditor();p=BladeParameters()
    try:
        editor.selector.setCurrentIndex(wall_index);editor.add_segment(field!="length")
        p.hub,p.shroud=editor.get_curves();editor.blade_edges.apply_to(p)
        before=physical_edges(p)
        key=("impeller_edges","leading_edge","hub","z")
        pending=editor.blade_edges.coordinate_controls[key].value()+.125
        editor.blade_edges.coordinate_controls[key].setValue(pending)
        index=len(editor.curves[wall_index].segments)-1
        editor._segment_changed(index,field,value)
        assert getattr(editor.curves[wall_index].segments[index],field)==value
        p.hub,p.shroud=editor.get_curves();editor.blade_edges.apply_to(p)
        np.testing.assert_allclose(physical_edges(p),before,atol=2e-12,rtol=0)
        assert editor.blade_edges.coordinate_controls[key].value()==pending
    finally:editor.close();editor.deleteLater();app.processEvents()


@pytest.mark.parametrize("edit",["length","radius","sweep_deg","type","start"])
def test_edit_that_moves_endpoint_updates_wall_and_coordinates(app,edit):
    editor=MeridionalEditor();p=BladeParameters()
    try:
        before=editor.get_curves();edges=deepcopy(editor.blade_edges.edges)
        point_before=physical_edges(p)
        if edit=="length":editor.table.cellWidget(0,1).setValue(27)
        elif edit=="type":editor.table.cellWidget(1,0).setCurrentIndex(0)
        elif edit=="start":editor.start_controls["start_z"].setValue(3)
        else:editor._segment_changed(1,edit,{"radius":31,"sweep_deg":85}[edit])
        assert editor.get_curves()!=before and editor.blade_edges.edges!=edges
        assert "ERROR" not in editor.message.text()
        p.hub,p.shroud=editor.get_curves();editor.blade_edges.apply_to(p)
        points=physical_edges(p)
        assert not np.allclose(points[:,0],point_before[:,0])
        np.testing.assert_array_equal(points[:,1],point_before[:,1])
        for key,side,wall,axis in editor.blade_edges.coordinate_controls:
            offset=(0 if key=="impeller_edges" else 2)+(0 if side=="leading_edge" else 1)
            expected=points[offset,0 if wall=="hub" else 1,1 if axis=="r" else 0]
            assert editor.blade_edges.coordinate_controls[key,side,wall,axis].value()==pytest.approx(expected,abs=1e-12)
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_invalid_wall_still_rejected(app):
    editor=MeridionalEditor()
    try:
        before=editor.get_curves();edges=deepcopy(editor.blade_edges.edges)
        editor._segment_changed(1,"radius",-1)
        assert editor.get_curves()==before and editor.blade_edges.edges==edges
        assert "無効な子午面" in editor.message.text()
    finally:editor.close();editor.deleteLater();app.processEvents()


@pytest.mark.parametrize("wall_index",[0,1])
def test_wall_dimension_edit_all_rows_undo_and_json(app,tmp_path,wall_index):
    w=MainWindow();w.show();app.processEvents()
    try:
        w.add_blade_row("impeller","独立翼列")
        w.meridional_editor.selector.setCurrentIndex(wall_index)
        before=deepcopy(w.get_parameters());count=w.undo_stack.count()
        reference=[physical_edges(row.parameters) for row in before.blade_rows]
        box=w.meridional_editor.table.cellWidget(2,1);box.setValue(65);box.editingFinished.emit()
        after=deepcopy(w.get_parameters());assert after!=before
        assert w.undo_stack.count()==count+1
        for row,points in zip(after.blade_rows,reference):
            p=deepcopy(row.parameters);p.hub,p.shroud=after.hub,after.shroud
            np.testing.assert_allclose(physical_edges(p),points,atol=2e-12,rtol=0)
        w.undo();assert w.get_parameters()==before
        w.redo();assert w.get_parameters()==after
        path=tmp_path/"wall-edit.json";w.save_to_path(path);w.load_from_path(path)
        assert w.get_parameters()==after
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_nonselected_row_endpoint_adjusts_to_shortened_wall(app,tmp_path):
    w=MainWindow();w.show();app.processEvents()
    try:
        w.add_blade_row("impeller","選択翼列")
        w.meridional_editor.blade_edges.row_controls["row-1","trailing_edge","hub"].setValue(.999)
        w.commit_edit();before=deepcopy(w.get_parameters());count=w.undo_stack.count()
        w.meridional_editor.table.cellWidget(2,1).setValue(54)
        w.commit_edit()
        after=deepcopy(w.get_parameters())
        assert after.hub.segments[2].length==54 and w.undo_stack.count()==count+1
        assert after.blade_rows[0].parameters.impeller_edges.trailing_edge.hub_m_flow_norm==1
        assert after.shroud==before.shroud
        assert after.blade_rows[0].parameters.impeller_edges.trailing_edge.shroud_m_flow_norm==before.blade_rows[0].parameters.impeller_edges.trailing_edge.shroud_m_flow_norm
        w.undo();assert w.get_parameters()==before
        w.redo();assert w.get_parameters()==after
        # Accept the wall edit even when snapping to its outlet makes a blade
        # invalid; the existing save validator must still protect the output.
        path=tmp_path/"shortened.json"
        with pytest.raises(ValueError,match="repeated points"):
            w.save_to_path(path)
        assert not path.exists() and w.get_parameters()==after
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()


@pytest.mark.parametrize("wall_index",[0,1])
def test_width_edit_adjusts_le_to_new_radius_and_undo_json(app,tmp_path,wall_index):
    w=MainWindow();w.show();app.processEvents()
    try:
        w.add_blade_row("impeller","幅編集")
        editor=w.meridional_editor;editor.selector.setCurrentIndex(wall_index)
        before=deepcopy(w.get_parameters());count=w.undo_stack.count()
        point_before=physical_edges(before)
        radius=getattr(before,("hub","shroud")[wall_index]).start_r+2
        box=editor.start_controls["start_r"];box.setValue(radius);box.editingFinished.emit()
        after=deepcopy(w.get_parameters());points=physical_edges(after)
        assert getattr(after,("hub","shroud")[wall_index]).start_r==radius
        assert points[0,wall_index,1]==pytest.approx(radius,abs=1e-12)
        assert points[0,wall_index,0]==pytest.approx(point_before[0,wall_index,0],abs=1e-12)
        np.testing.assert_array_equal(points[:,1-wall_index],point_before[:,1-wall_index])
        assert w.undo_stack.count()==count+1
        for row in after.blade_rows:
            p=deepcopy(row.parameters);p.hub,p.shroud=after.hub,after.shroud
            assert physical_edges(p)[0,wall_index,1]==pytest.approx(radius,abs=1e-12)
        w.undo();assert w.get_parameters()==before
        w.redo();assert w.get_parameters()==after
        path=tmp_path/"widened.json";w.save_to_path(path);w.load_from_path(path)
        assert w.get_parameters()==after
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()


@pytest.mark.parametrize("arc",[False,True])
@pytest.mark.parametrize("wall_index",[0,1])
def test_appending_segment_preserves_applied_rz_and_pending_input(app,arc,wall_index):
    editor=MeridionalEditor();p=BladeParameters()
    try:
        editor.blade_edges.set_parameters(p)
        before=physical_edges(p)
        editor.selector.setCurrentIndex(wall_index)
        pending_key=("impeller_edges","leading_edge","hub","z")
        pending=editor.blade_edges.coordinate_controls[pending_key].value()+.25
        editor.blade_edges.coordinate_controls[pending_key].setValue(pending)
        editor.add_segment(arc)
        after=deepcopy(p);after.hub,after.shroud=editor.get_curves();editor.blade_edges.apply_to(after)
        np.testing.assert_allclose(physical_edges(after),before,rtol=0,atol=2e-12)
        assert editor.blade_edges.coordinate_controls[pending_key].value()==pending
        assert len(getattr(after,("hub","shroud")[wall_index]).segments)==len(getattr(p,("hub","shroud")[wall_index]).segments)+1
        # A second addition keeps the same saved points and unapplied text.
        editor.add_segment(arc)
        after.hub,after.shroud=editor.get_curves();editor.blade_edges.apply_to(after)
        np.testing.assert_allclose(physical_edges(after),before,rtol=0,atol=2e-12)
        assert editor.blade_edges.coordinate_controls[pending_key].value()==pending
    finally:editor.close();editor.deleteLater();app.processEvents()


@pytest.mark.parametrize("arc",[False,True])
@pytest.mark.parametrize("wall_index",[0,1])
def test_segment_append_keeps_all_row_edges_with_single_undo_and_json(app,tmp_path,arc,wall_index):
    w=MainWindow();w.show();app.processEvents()
    try:
        w.add_blade_row("impeller","追加翼列")
        w.meridional_editor.selector.setCurrentIndex(wall_index)
        w.navigator.tree.setCurrentItem(w.navigator.meridional_item)
        before=deepcopy(w.get_parameters());history=w.undo_stack.count()
        reference=[physical_edges(row.parameters) for row in before.blade_rows]
        w.meridional_editor.add_segment(arc)
        after=deepcopy(w.get_parameters())
        assert w.undo_stack.count()==history+1
        np.testing.assert_allclose(physical_edges(after),physical_edges(before),rtol=0,atol=2e-12)
        for row,points in zip(after.blade_rows,reference):
            p=deepcopy(row.parameters);p.hub,p.shroud=after.hub,after.shroud
            np.testing.assert_allclose(physical_edges(p),points,rtol=0,atol=2e-12)
        w.undo();assert w.get_parameters()==before
        w.redo();assert w.get_parameters()==after
        path=tmp_path/"extended.json";w.save_to_path(path);w.load_from_path(path)
        assert w.get_parameters()==after
        for row in after.blade_rows:
            w.select_blade_row(row.identifier)
            np.testing.assert_allclose(physical_edges(w.get_parameters()),reference[after.blade_rows.index(row)],rtol=0,atol=2e-12)
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_wall_rescale_retains_other_wall_and_rejects_invalid_extension():
    p=BladeParameters();before=deepcopy(p.impeller_edges)
    rescale_extended_wall_edges(p.impeller_edges,"hub",100,125)
    assert p.impeller_edges.leading_edge.hub_m_flow_norm==before.leading_edge.hub_m_flow_norm*.8
    assert p.impeller_edges.leading_edge.shroud_m_flow_norm==before.leading_edge.shroud_m_flow_norm
    assert p.impeller_edges.trailing_edge.shroud_m_flow_norm==before.trailing_edge.shroud_m_flow_norm
    for wall,a,b in (("tip",100,125),("hub",0,125),("hub",125,100),("hub",100,float("nan"))):
        with pytest.raises(ValueError):rescale_extended_wall_edges(p.impeller_edges,wall,a,b)


@pytest.mark.parametrize("key",["impeller_edges","diffuser_edges"])
@pytest.mark.parametrize("side",["leading_edge","trailing_edge"])
@pytest.mark.parametrize("wall",["hub","shroud"])
def test_physical_input_roundtrip_for_every_endpoint(app,key,side,wall):
    editor=BladeEdgeEditor(); p=BladeParameters(); before=deepcopy(p)
    try:
        original=getattr(getattr(p,key),side)
        fraction=getattr(original,wall+"_m_flow_norm")+.003
        geometry=generate_meridional(getattr(p,wall))
        z,r=sample_meridional(geometry,np.array([fraction*geometry.length]))[0]
        editor.coordinate_controls[key,side,wall,"r"].setValue(r)
        editor.coordinate_controls[key,side,wall,"z"].setValue(z)
        editor.apply_to(p);assert p==before  # paired coordinates wait for Apply
        editor.apply_button.click();editor.apply_to(p)
        assert getattr(getattr(getattr(p,key),side),wall+"_m_flow_norm")==pytest.approx(fraction,abs=1e-13)
        assert all(box.isHidden() for box in editor.controls.values())
        assert editor.table.horizontalHeaderItem(2).text()=="R [mm]"
        assert editor.table.horizontalHeaderItem(3).text()=="Z [mm]"
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_off_wall_input_projects_to_corresponding_wall_and_noop_keeps_precision(app):
    editor=BladeEdgeEditor();p=BladeParameters()
    try:
        before=deepcopy(p);editor.apply_button.click();editor.apply_to(p);assert p==before
        # Hub inlet is an axial straight line R=50; off-wall R must snap to 50.
        key=("impeller_edges","leading_edge","hub")
        editor.coordinate_controls[*key,"r"].setValue(48.)
        editor.coordinate_controls[*key,"z"].setValue(10.)
        editor.apply_button.click();editor.apply_to(p)
        assert editor.coordinate_controls[*key,"r"].value()==50.
        assert editor.coordinate_controls[*key,"z"].value()==10.
        assert p.impeller_edges.leading_edge.hub_m_flow_norm==pytest.approx(10/generate_meridional(p.hub).length)
        assert p.impeller_edges.leading_edge.shroud_m_flow_norm==before.impeller_edges.leading_edge.shroud_m_flow_norm
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_wall_changes_and_drag_refresh_physical_fields(app):
    editor=BladeEdgeEditor();p=BladeParameters()
    try:
        p.hub.start_z+=2;editor.set_parameters(p)
        key=("impeller_edges","leading_edge","hub")
        editor.move_endpoint(*key,.2)
        z,r=sample_meridional(generate_meridional(p.hub),np.array([.2*generate_meridional(p.hub).length]))[0]
        assert editor.coordinate_controls[*key,"r"].value()==pytest.approx(r,abs=1e-12)
        assert editor.coordinate_controls[*key,"z"].value()==pytest.approx(z,abs=1e-12)
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_apply_rz_is_one_undo_and_save_load_keeps_legacy_schema(app,tmp_path):
    w=MainWindow();w.show();app.processEvents();w._select_meridional()
    try:
        before=deepcopy(w.get_parameters()); count=w.undo_stack.count()
        editor=w.meridional_editor.blade_edges
        for wall in ("hub","shroud"):
            geometry=generate_meridional(getattr(before,wall))
            fraction=getattr(before.impeller_edges.leading_edge,wall+"_m_flow_norm")+.003
            z,r=sample_meridional(geometry,np.array([fraction*geometry.length]))[0]
            editor.coordinate_controls["impeller_edges","leading_edge",wall,"r"].setValue(r)
            editor.coordinate_controls["impeller_edges","leading_edge",wall,"z"].setValue(z)
        editor.apply_button.click();w.update_geometry()
        after=deepcopy(w.get_parameters());assert after!=before
        assert w.undo_stack.count()==count+1
        w.undo();assert w.get_parameters()==before
        w.redo();assert w.get_parameters()==after
        assert w.central_views.currentWidget() is w.meridional_editor.context
        path=tmp_path/"rz.json";w.save_to_path(path)
        assert load_project(path)==after
        assert '"hub_m_flow_norm"' in path.read_text() and '"coordinate_controls"' not in path.read_text()
        w.load_from_path(path);assert w.get_parameters()==after
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()
