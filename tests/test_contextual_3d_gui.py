import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.blade_rows import initial_rows
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.row_domain import preview_wall_chunks,wall_interval
from blade_designer.geometry.meridional_segments import sample_meridional


def assigned_project():
    p=BladeParameters()
    for wall in ("hub","shroud"):
        setattr(p.impeller_edges.trailing_edge,wall+"_m_flow_norm",.4)
        for i,s in enumerate(getattr(p,wall).segments):s.blade_row="row-1" if i<2 else "row-2"
    p.blade_rows=initial_rows(p);p.active_blade_row="row-1"
    p.geometry.vane_count=p.blade_rows[0].parameters.geometry.vane_count=2
    p.blade_rows[1].parameters.geometry.vane_count=3
    return p


def test_preview_wall_chunks_use_analytic_endpoints_without_bridging_gaps():
    p=assigned_project()
    p.hub.segments[1].blade_row="row-2";p.hub.segments[2].blade_row="row-1"
    before=deepcopy(p);g=generate_impeller(p)
    chunks=preview_wall_chunks(p,g,"row-1")
    assert len(chunks["hub"])==2 and len(chunks["shroud"])==1 and p==before
    boundaries=np.r_[0.,np.cumsum([s.length for s in g.hub.segments])]
    for chunk,i in zip(chunks["hub"],[0,2]):
        actual=np.column_stack((chunk.z,chunk.r))[[0,-1]]
        np.testing.assert_allclose(actual,sample_meridional(g.hub,boundaries[[i,i+1]]),atol=1e-12)


def test_preview_wall_chunks_legacy_and_missing_assignment():
    p=BladeParameters();g=generate_impeller(p)
    chunks=preview_wall_chunks(p,g,None)
    assert chunks["hub"]==[g.hub] and chunks["shroud"]==[g.shroud]
    p.hub.segments[0].blade_row="row-1"
    chunks=preview_wall_chunks(p,g,"row-1")
    assert len(chunks["hub"])==1 and chunks["shroud"]==[]
    assert preview_wall_chunks(p,g,"row-2")=={"hub":[],"shroud":[]}


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    w.set_parameters(assigned_project());w._reset_history();w.update_geometry()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_meridional_all_rows_annulus_uses_independent_counts_and_camera(window,monkeypatch):
    w=window;before=deepcopy(w.get_parameters());count=w.undo_stack.count()
    camera=deepcopy(w.model_preview_3d.camera_position)
    w._select_meridional();v=w.model_preview_3d
    names=["Impeller [row-1] Hub camber","Diffuser [row-2] Hub camber"]
    assert all(name in v.base_lines for name in names)
    assert len(v.spanwise_lines)==488 and "All blade rows (2)" in v.model_label
    assert list(v.surfaces)==["hub","shroud"]
    calls=[];original=w.designer.generate_diffuser_3d
    monkeypatch.setattr(w.designer,"generate_diffuser_3d",lambda p:(calls.append(1),original(p))[1])
    w.annulus_3d.setChecked(True);w.annulus_2d.setChecked(True)
    assert calls==[]  # display switches reuse the current geometry
    for name,n in zip(names,[2,3]):
        assert len([key for key in v.lines if key.startswith(name+" • blade ")])==n
        original_points=v.base_lines[name][0]
        sampled=original_points[np.linspace(0,len(original_points)-1,min(len(original_points),151),dtype=int)]
        actual=v.lines[name+" • blade 2"][0]
        np.testing.assert_array_equal(actual[:,2],sampled[:,2])
        theta=2*np.pi/n
        np.testing.assert_allclose(actual[:,0],sampled[:,0]*np.cos(theta)-sampled[:,1]*np.sin(theta),atol=1e-12)
    assert w.get_parameters()==before and w.undo_stack.count()==count
    for key,value in camera.items():np.testing.assert_array_equal(v.camera_position[key],value)


@pytest.mark.parametrize("identifier",["row-1","row-2"])
def test_selected_row_has_its_profile_and_only_owned_revolved_walls(window,identifier):
    w=window;w._select_meridional();w.select_blade_row(identifier);w.update_geometry()
    p=w.get_parameters();v=w.model_preview_3d
    g=w.impeller_geometry if identifier=="row-1" else w.diffuser_geometry
    np.testing.assert_array_equal(v.base_lines["Hub camber"][0],g.sections[0].camber.xyz)
    assert not any("[row-" in name for name in v.base_lines)
    for name in ("hub","shroud"):
        wall=getattr(g,name);start,end=wall_interval(getattr(p,name),wall,identifier)
        points=sample_meridional(wall,np.array([start,end]))
        actual=v.base_lines[name.title()][0]
        np.testing.assert_allclose(actual[[0,-1]],np.column_stack((points[:,1],np.zeros(2),points[:,0])),atol=1e-12)
        faces=v.surfaces[name][0]
        assert faces[:,:,2].min()>=min(points[:,0])-1e-12
        assert faces[:,:,2].max()<=max(points[:,0])+1e-12
    v.fit_view();assert not v.grab().toImage().isNull()


def test_meridional_edit_undo_and_json_update_all_rows(window,tmp_path):
    w=window;w._select_meridional();before=deepcopy(w.get_parameters())
    name="Impeller [row-1] Hub camber"
    reference=w.model_preview_3d.base_lines[name][0].copy()
    diffuser=w.model_preview_3d.base_lines["Diffuser [row-2] Hub camber"][0].copy()
    box=w.angle_editor.table.cellWidget(1,1);box.setValue(box.value()-3);box.editingFinished.emit()
    w.update_geometry()
    changed=w.model_preview_3d.base_lines[name][0].copy()
    assert not np.allclose(reference,changed)
    np.testing.assert_array_equal(diffuser,w.model_preview_3d.base_lines["Diffuser [row-2] Hub camber"][0])
    w.undo();assert w.get_parameters()==before
    np.testing.assert_array_equal(reference,w.model_preview_3d.base_lines[name][0])
    w.redo();np.testing.assert_array_equal(changed,w.model_preview_3d.base_lines[name][0])
    path=tmp_path/"assigned.json";w.save_to_path(path);w.load_from_path(path);w._select_meridional()
    np.testing.assert_array_equal(changed,w.model_preview_3d.base_lines[name][0])


def test_partial_invalid_row_does_not_hide_valid_all_rows(window):
    w=window;p=w.get_parameters()
    row=p.blade_rows[1]
    row.parameters.diffuser_profile.blade_angle.points[1].value=29
    row.parameters.diffuser_profile.thickness.points[1].value=7
    w.set_parameters(p);w.update_geometry();w._select_meridional()
    assert "Impeller [row-1] Hub camber" in w.model_preview_3d.base_lines
    assert "Diffuser [row-2] Hub camber" not in w.model_preview_3d.base_lines
    assert "3D Diffuser" in w.messages.toPlainText() and "row omitted" in w.messages.toPlainText()


def test_invalid_row_wall_is_not_displayed_as_a_valid_row(window,monkeypatch):
    from blade_designer.geometry import preview_computation
    original=preview_computation.preview_wall_chunks
    def unavailable(p,g,identifier):
        if identifier=="row-2":raise ValueError("analysis wall unavailable")
        return original(p,g,identifier)
    monkeypatch.setattr(preview_computation,"preview_wall_chunks",unavailable)
    w=window;before=deepcopy(w.get_parameters());camera=deepcopy(w.model_preview_3d.camera_position)
    w._select_meridional()
    assert "Impeller [row-1] Hub camber" in w.model_preview_3d.base_lines
    assert "Diffuser [row-2] Hub camber" not in w.model_preview_3d.base_lines
    assert "analysis wall unavailable (row omitted)" in w.messages.toPlainText()
    assert w.get_parameters()==before
    for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)


def test_ownership_change_undo_refreshes_selected_wall_extent(window):
    w=window;before=deepcopy(w.model_preview_3d.surfaces["hub"][0])
    box=w.meridional_editor.table.cellWidget(1,5)
    box.setCurrentIndex(box.findData("row-2"));w.update_geometry()
    assert w.model_preview_3d.base_lines["Hub"][0][-1,2]==pytest.approx(25)
    w.undo();np.testing.assert_array_equal(before,w.model_preview_3d.surfaces["hub"][0])


def test_pending_edit_and_display_switch_render_recalculated_selected_geometry(window):
    w=window;original=w.model_preview_3d.base_lines["Hub camber"][0].copy()
    box=w.angle_editor.table.cellWidget(1,1);box.setValue(box.value()-3)
    w.annulus_3d.setChecked(True);w.update_geometry()
    current=w.impeller_geometry.sections[0].camber.xyz
    assert not np.allclose(original,current)
    np.testing.assert_array_equal(w.model_preview_3d.base_lines["Hub camber"][0],current)
