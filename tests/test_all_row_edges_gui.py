import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.geometry.blade_edge import edge_endpoints
from blade_designer.geometry.meridional_segments import generate_meridional,sample_meridional


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def own_edges(p):
    return {row.identifier:deepcopy(getattr(row.parameters,row.kind+"_edges")) for row in p.blade_rows}


def physical_own_edges(p):
    walls=[generate_meridional(getattr(p,name)) for name in ("hub","shroud")]
    return {key:np.array([edge_endpoints(getattr(edges,side),*walls) for side in ("leading_edge","trailing_edge")])
            for key,edges in own_edges(p).items()}


def test_add_rc_keeps_diffuser_group_and_adds_table_and_handles(window):
    w=window;w.select_blade_row("row-2");before=deepcopy(w.get_parameters().diffuser_edges)
    w.add_blade_row("diffuser","RC");p=w.get_parameters();e=w.meridional_editor.blade_edges
    rc=p.active_blade_row
    assert e.table.rowCount()==12
    assert [e.table.item(i,0).text() for i in range(0,12,4)]==["Impeller","Diffuser","RC"]
    assert own_edges(p)["row-2"]==before and own_edges(p)[rc]==before
    assert e.row_edges["row-2"] is not e.row_edges[rc]
    assert e.row_edges["row-2"].leading_edge is not e.row_edges[rc].leading_edge
    for context in (w.context_meridional,w.meridional_editor.context):
        assert len(context.edge_handles)==6
        assert {item.key for item in context.edge_handles}=={"row-1","row-2",rc}
        assert {item.label.toPlainText() for item in context.edge_handles}=={
            "Impeller LE","Impeller TE","Diffuser LE","Diffuser TE","RC LE","RC TE"}
    w.select_blade_row("row-1");w._select_meridional()
    assert e.table.item(4,0).text()=="Diffuser" and e.table.item(8,0).text()=="RC"


def test_nonselected_rc_rz_edit_is_independent_one_undo_and_json(window,tmp_path):
    w=window;w.add_blade_row("diffuser","RC");rc=w.get_parameters().active_blade_row
    w.select_blade_row("row-1");w._select_meridional();before=deepcopy(w.get_parameters())
    e=w.meridional_editor.blade_edges;count=w.undo_stack.count()
    wall=generate_meridional(before.hub);z,r=sample_meridional(wall,np.array([.88*wall.length]))[0]
    e.all_coordinate_controls[rc,"leading_edge","hub","r"].setValue(r)
    e.all_coordinate_controls[rc,"leading_edge","hub","z"].setValue(z)
    assert w.get_parameters()==before
    e.apply_button.click();w.update_geometry();after=deepcopy(w.get_parameters())
    assert own_edges(after)[rc].leading_edge.hub_m_flow_norm==pytest.approx(.88,abs=1e-12)
    assert own_edges(after)["row-2"]==own_edges(before)["row-2"]
    assert own_edges(after)["row-1"]==own_edges(before)["row-1"]
    assert w.undo_stack.count()==count+1
    w.undo();assert w.get_parameters()==before
    w.redo();assert w.get_parameters()==after
    path=tmp_path/"all-edges.json";w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters()==after and e.table.rowCount()==12
    w.select_blade_row("row-2");assert w.get_parameters().diffuser_edges==own_edges(before)["row-2"]
    w.select_blade_row(rc);assert w.get_parameters().diffuser_edges==own_edges(after)[rc]


def test_rc_drag_key_changes_only_rc_with_float_precision(window):
    w=window;w.add_blade_row("diffuser","RC");rc=w.get_parameters().active_blade_row
    w.select_blade_row("row-1");w._select_meridional();before=deepcopy(w.get_parameters())
    context=w.meridional_editor.context;count=w.undo_stack.count();value=.8871234567890123
    context.edgeDragStarted.emit();context.endpointMoved.emit(rc,"leading_edge","hub",value)
    context.edgeDragFinished.emit();w.update_geometry();after=w.get_parameters()
    assert own_edges(after)[rc].leading_edge.hub_m_flow_norm==value
    assert own_edges(after)["row-2"]==own_edges(before)["row-2"]
    assert w.undo_stack.count()==count+1
    item=next(item for item in context.edge_handles if item.key==rc and item.side=="leading_edge")
    np.testing.assert_allclose(item.pos,physical_own_edges(after)[rc][0],atol=1e-12)
    w.undo();assert w.get_parameters()==before


def test_rename_reorder_delete_and_undo_preserve_all_edge_groups(window):
    w=window;w.add_blade_row("diffuser","RC");rc=w.get_parameters().active_blade_row
    e=w.meridional_editor.blade_edges;e.row_controls[rc,"leading_edge","hub"].setValue(.88);w.commit_edit()
    reference=own_edges(w.get_parameters())
    w.rename_blade_row(rc,"Return channel")
    assert e.table.item(8,0).text()=="Return channel" and e.table.item(4,0).text()=="Diffuser"
    assert next(item for item in w.meridional_editor.context.edge_handles if item.key==rc).label.toPlainText()=="Return channel LE"
    w.move_blade_row(-1)
    assert [e.table.item(i,0).text() for i in range(0,12,4)]==["Impeller","Return channel","Diffuser"]
    assert own_edges(w.get_parameters())==reference
    w.delete_blade_row();assert e.table.rowCount()==8 and len(w.meridional_editor.context.edge_handles)==4
    assert own_edges(w.get_parameters())["row-2"]==reference["row-2"]
    w.undo();assert e.table.rowCount()==12 and own_edges(w.get_parameters())==reference


@pytest.mark.parametrize("wall_index",[0,1])
def test_wall_extension_keeps_every_row_edge_and_pending_rc_input(window,wall_index):
    w=window;w.add_blade_row("diffuser","RC");rc=w.get_parameters().active_blade_row
    w.select_blade_row("row-1");before=w.get_parameters();reference=physical_own_edges(before)
    e=w.meridional_editor.blade_edges;key=(rc,"leading_edge","hub","z")
    pending=e.all_coordinate_controls[key].value()+.25;e.all_coordinate_controls[key].setValue(pending)
    w.meridional_editor.selector.setCurrentIndex(wall_index);w.meridional_editor.add_segment(False)
    assert e.all_coordinate_controls[key].value()==pending
    after=w.get_parameters()
    for identifier,points in physical_own_edges(after).items():np.testing.assert_allclose(points,reference[identifier],atol=2e-12,rtol=0)


def test_edge_group_count_matches_rows_when_a_kind_is_removed(window):
    w=window;w.select_blade_row("row-2");w.delete_blade_row()
    assert w.meridional_editor.blade_edges.table.rowCount()==4
    assert len(w.meridional_editor.context.edge_handles)==2
    w.add_blade_row("impeller","Second impeller");w.add_blade_row("diffuser","Diffuser")
    w.add_blade_row("diffuser","RC")
    p=w.get_parameters();assert len(p.blade_rows)==4
    assert w.meridional_editor.blade_edges.table.rowCount()==16
    assert len(w.meridional_editor.context.edge_handles)==8
