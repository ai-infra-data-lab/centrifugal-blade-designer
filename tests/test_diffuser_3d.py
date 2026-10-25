"""Analytic wall placement and span topology; no historical fixture changes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.geometry.geometry_3d import generate_diffuser_3d
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.geometry.wireframe import build_spanwise_wireframe
from blade_designer.models.parameters import (BladeParameters,BladeAngleParameters,
    DistributionPoint,EdgeType,RotationDirection)
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.gui.main_window import MainWindow


def conical_parameters():
    p=BladeParameters()
    p.hub=MeridionalCurveParameters(10,50,30,[LineSegmentParameters(200)])
    p.shroud=MeridionalCurveParameters(15,65,30,[LineSegmentParameters(200)])
    for wall in ("hub","shroud"):
        setattr(p.diffuser_edges.leading_edge,wall+"_m_flow_norm",.2)
        setattr(p.diffuser_edges.trailing_edge,wall+"_m_flow_norm",.7)
    p.diffuser_profile.blade_angle=BladeAngleParameters([DistributionPoint(0,20),DistributionPoint(1,20)])
    return p


@pytest.mark.parametrize("direction",list(RotationDirection))
@pytest.mark.parametrize("edge_type",list(EdgeType))
def test_diffuser_sections_on_cones_with_analytic_angle_and_closed_joins(direction,edge_type):
    p=conical_parameters();p.rotation_direction=direction
    p.diffuser_profile.edge_parameters.te_type=edge_type
    before=deepcopy(p);g=generate_diffuser_3d(p)
    assert p==before and [s.span for s in g.sections]==[0,1]
    for s in g.sections:
        for fraction,index in ((.2,0),(.7,-1)):
            np.testing.assert_allclose([s.camber.z[index],s.camber.r[index]],
                [10+5*s.span+200*fraction*np.cos(np.pi/6),
                 50+15*s.span+200*fraction*np.sin(np.pi/6)],atol=1e-11)
        expected=direction.sign*np.tan(np.deg2rad(20))/np.sin(np.pi/6)*np.log(s.camber.r/s.camber.r[0])
        np.testing.assert_allclose(s.camber.theta_rad,expected,atol=1e-7)
        for name in ("camber","master_ps","master_ss","master_le","master_te"):
            c=getattr(s,name)
            assert np.isfinite(c.xyz).all()
            np.testing.assert_allclose(c.r,50+15*s.span+(c.z-10-5*s.span)*np.tan(np.pi/6),atol=1e-11)
        for a,b,ia,ib in ((s.le,s.ps,-1,0),(s.ps,s.te,-1,0),(s.te,s.ss,-1,-1),(s.ss,s.le,0,0)):
            np.testing.assert_array_equal(a.xyz[ia],b.xyz[ib])
    lines=build_spanwise_wireframe(g.sections)
    assert len(lines)==sum(getattr(p.output_points,name+"_points") for name in ("le","ps","te","ss"))
    for line in lines:
        expected=np.array([getattr(s,line.segment.lower()).xyz[line.segment_index] for s in g.sections])
        np.testing.assert_array_equal(line.xyz,expected)
        np.testing.assert_array_equal(line.spans,[0,1])


def test_diffuser_3d_uses_own_profile_edges_and_preserves_2d_and_json(tmp_path):
    p=conical_parameters();engine=BladeDesigner()
    planar=engine.generate_diffuser(p);g=engine.generate_diffuser_3d(p)
    p.sections[0].blade_angle.points[1].value=40
    p.impeller_edges.leading_edge.hub_m_flow_norm=.17
    unchanged=engine.generate_diffuser_3d(p)
    for a,b in zip(g.sections,unchanged.sections):np.testing.assert_array_equal(a.master_ps.xyz,b.master_ps.xyz)
    p.diffuser_profile.blade_angle.points[0].value=25
    p.diffuser_edges.leading_edge.hub_m_flow_norm=.22
    changed=engine.generate_diffuser_3d(p)
    assert not np.allclose(g.sections[0].camber.xyz,changed.sections[0].camber.xyz)
    for span in (0,1):
        assert not np.allclose(g.sections[span].camber.theta_rad,changed.sections[span].camber.theta_rad)
    # 3D generation leaves the existing radial 2D engine and its CSV inputs intact.
    original=conical_parameters();engine.generate_diffuser_3d(original)
    after=engine.generate_diffuser(original)
    np.testing.assert_array_equal(planar.master_surfaces.ps.xy,after.master_surfaces.ps.xy)
    path=tmp_path/"diffuser.json";save_project(path,p)
    restored=engine.generate_diffuser_3d(load_project(path))
    for a,b in zip(changed.sections,restored.sections):np.testing.assert_array_equal(a.master_ss.xyz,b.master_ss.xyz)


def test_diffuser_hub_and_shroud_follow_axial_wall_motion():
    p=conical_parameters();before=generate_diffuser_3d(p)
    p.hub.start_z+=8;p.shroud.start_z+=8
    after=generate_diffuser_3d(p)
    for a,b in zip(before.sections,after.sections):
        np.testing.assert_allclose(a.camber.xyz+[0,0,8],b.camber.xyz,atol=1e-11)


@pytest.mark.parametrize("invalid",["profile","edges","wall"])
def test_invalid_diffuser_3d_rejected_without_mutating_parameters(invalid):
    p=conical_parameters()
    if invalid=="profile":p.diffuser_profile.span=.5
    elif invalid=="edges":p.diffuser_edges.trailing_edge.hub_m_flow_norm=.1
    else:p.hub.segments[0].length=-1
    before=deepcopy(p)
    with pytest.raises(ValueError):generate_diffuser_3d(p)
    assert p==before


def test_diffuser_3d_gui_preview_tracks_profile_undo_and_json(tmp_path):
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    try:
        w.select_blade_row("row-2");w.update_geometry()
        before=deepcopy(w.get_parameters());camera=deepcopy(w.model_preview_3d.camera_position)
        reference=w.diffuser_geometry.sections[0].camber.xyz.copy()
        assert len(w.model_preview_3d.spanwise_lines)>0
        for preview in (w.preview_3d,w.model_preview_3d):
            np.testing.assert_array_equal(preview.base_lines["Hub camber"][0],reference)
            np.testing.assert_array_equal(preview.base_lines["Tip camber"][0],w.diffuser_geometry.sections[-1].camber.xyz)
        box=w.angle_editor.table.cellWidget(1,1);box.setValue(box.value()-3)
        box.editingFinished.emit();w.commit_edit();w.update_geometry()
        after=deepcopy(w.get_parameters());changed=w.diffuser_geometry.sections[0].camber.xyz.copy()
        assert not np.allclose(reference,changed)
        w.undo();np.testing.assert_array_equal(w.diffuser_geometry.sections[0].camber.xyz,reference)
        assert w.get_parameters()==before
        w.redo();np.testing.assert_array_equal(w.diffuser_geometry.sections[0].camber.xyz,changed)
        for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)
        path=tmp_path/"gui-diffuser.json";w.save_to_path(path);w.load_from_path(path)
        assert w.get_parameters()==after
        np.testing.assert_array_equal(w.diffuser_geometry.sections[0].camber.xyz,changed)
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_invalid_diffuser_3d_keeps_last_preview_but_updates_valid_2d(monkeypatch):
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    try:
        w.select_blade_row("row-2");w.update_geometry()
        previous=w.diffuser_geometry
        lines=w.model_preview_3d.base_lines
        label=w.model_preview_3d.model_label
        original_angle=w.angle_editor.table.cellWidget(1,1).value()
        # Thickness 7 fits after nose positioning. Inject a generation failure
        # to retain this test's last-valid-preview contract independently.
        generate=w.designer.generate_diffuser_3d
        def fail_thick_profile(params):
            if max(point.value for point in params.diffuser_profile.thickness.points)>6:
                raise ValueError('Injected invalid Diffuser 3D geometry')
            return generate(params)
        monkeypatch.setattr(w.designer,'generate_diffuser_3d',fail_thick_profile)
        w.angle_editor.table.cellWidget(1,1).setValue(29)
        w.thickness_editor.table.cellWidget(1,1).setValue(7)
        w.update_geometry()
        assert w.geometry.thickness.max()==pytest.approx(7)
        assert w.diffuser_geometry is previous and w.model_preview_3d.base_lines is lines
        assert "ERROR — Diffuser 3D" in w.messages.toPlainText()
        assert "last valid geometry" in w.messages.toPlainText()
        w.update_geometry();assert w.model_preview_3d.model_label==label
        w.thickness_editor.table.cellWidget(1,1).setValue(4)
        w.angle_editor.table.cellWidget(1,1).setValue(original_angle);w.update_geometry()
        assert w.diffuser_geometry is not previous
        assert "ERROR — Diffuser 3D" not in w.messages.toPlainText()
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()
