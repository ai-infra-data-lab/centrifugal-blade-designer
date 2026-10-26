"""Analytic corner geometry, legacy bytes and persistent element constraints."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import numpy as np
import pytest
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters,ArcSegmentParameters
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.blade_rows import initial_rows,row_parameters,validate_rows
from blade_designer.geometry.meridional_segments import generate_meridional,convert_segment_type
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.preview_job import snapshot_text
from tests.test_meridional_elements import project,duct


@pytest.mark.parametrize('turn',[-70.,-25.,0.,20.,80.])
def test_two_lines_share_endpoint_and_have_exact_prescribed_turn(turn):
    p=MeridionalCurveParameters(2,100,10,[LineSegmentParameters(5),LineSegmentParameters(7,inlet_turn_deg=turn)])
    before=deepcopy(p);a,b=generate_meridional(p).segments
    np.testing.assert_array_equal(a.end.zr,b.start.zr)
    direction=np.array([np.cos(np.deg2rad(10+turn)),np.sin(np.deg2rad(10+turn))])
    np.testing.assert_allclose(b.start_tangent,direction,atol=1e-14)
    np.testing.assert_allclose(b.end.zr,a.end.zr+7*direction,atol=1e-12)
    assert p==before


@pytest.mark.parametrize('clockwise',[True,False])
def test_line_arc_corner_has_analytic_center_end_and_following_tangent(clockwise):
    p=MeridionalCurveParameters(0,100,0,[LineSegmentParameters(10),
        ArcSegmentParameters(5,40,clockwise,inlet_turn_deg=30),LineSegmentParameters(2)])
    a,b,c=generate_meridional(p).segments
    phi=np.deg2rad(30);t=np.array([np.cos(phi),np.sin(phi)]);sign=-1 if clockwise else 1
    center=a.end.zr+sign*5*np.array([-t[1],t[0]])
    theta=np.deg2rad(sign*40);rot=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    np.testing.assert_allclose(b.center.zr,center,atol=1e-12)
    np.testing.assert_allclose(b.end.zr,center+rot@(a.end.zr-center),atol=1e-12)
    np.testing.assert_array_equal(b.end.zr,c.start.zr)
    np.testing.assert_array_equal(b.end_tangent,c.start_tangent)


@pytest.mark.parametrize('value',[True,False,float('nan'),float('inf'),180.,-180.,'30',{}])
def test_invalid_angles_are_rejected(value):
    p=MeridionalCurveParameters(0,100,0,[LineSegmentParameters(10,inlet_turn_deg=value)])
    with pytest.raises(ValueError,match='Join turn'):generate_meridional(p)


def test_first_segment_uses_start_direction_as_datum_and_type_changes_keep_turn():
    p=MeridionalCurveParameters(0,100,10,[LineSegmentParameters(10,inlet_turn_deg=20)])
    tangent=generate_meridional(p).segments[0].start_tangent
    np.testing.assert_allclose(tangent,[np.cos(np.pi/6),np.sin(np.pi/6)])
    arc=convert_segment_type(p.segments[0],True);line=convert_segment_type(arc,False)
    assert arc.inlet_turn_deg==line.inlet_turn_deg==20
    assert line.length==pytest.approx(10)


def test_element_corner_uses_independent_hub_shroud_turns_and_tracks_parent():
    p=project();p.blade_rows.append(duct('duct','row-1'));row=p.blade_rows[-1]
    row.hub_inlet_turn_deg=20;row.shroud_inlet_turn_deg=-15
    before=deepcopy(p)
    for change in (0,6):
        p.hub.start_z=change
        child=row_parameters(p,row);parent=row_parameters(p,p.blade_rows[0])
        for name,angle in (('hub',20),('shroud',-15)):
            a=generate_meridional(getattr(parent,name)).segments[-1]
            b=generate_meridional(getattr(child,name)).segments[0]
            np.testing.assert_allclose(b.start.zr,a.end.zr,atol=1e-10)
            turn=np.rad2deg(np.arctan2(np.linalg.det(np.stack([a.end_tangent,b.start_tangent])),a.end_tangent@b.start_tangent))
            assert turn==pytest.approx(angle,abs=1e-10)
    assert row==before.blade_rows[-1]
    row.hub_inlet_turn_deg=float('nan')
    with pytest.raises(ValueError,match='Join turn'):validate_rows(p)


def test_corner_json_roundtrip_explicit_zero_and_invalid_shape_protects_file(tmp_path):
    p=project();p.hub.segments[1].inlet_turn_deg=2.;p.shroud.segments[1].inlet_turn_deg=0.
    path=tmp_path/'corners.json';save_project(path,p);assert load_project(path)==p
    assert snapshot_text(p)!=snapshot_text(project())
    before=path.read_bytes();p.hub.segments[1].inlet_turn_deg=180
    with pytest.raises(ValueError):save_project(path,p)
    assert path.read_bytes()==before


def test_pre_corner_default_and_row_disk_snapshot_bytes_match_frozen_baseline():
    from blade_designer.cad.client import json_text
    root=Path(__file__).parent/'fixtures'
    for case in ('default','rows_disk'):
        p=BladeParameters()
        if case=='rows_disk':
            p.cad_export.disk.backside=MeridionalCurveParameters(0,10,0,[LineSegmentParameters(10)])
            p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
        assert snapshot_text(p).encode()==(root/('pre_corner_'+case+'_preview.json')).read_bytes()
        assert json_text({'schema_version':'0.4',**asdict(p)}).encode()==(root/('pre_corner_'+case+'_cad.json')).read_bytes()


@pytest.mark.parametrize('angle,count',[(None,5),(10.,6)])
def test_turbogrid_wall_sampling_includes_exact_corner_without_changing_g1_counts(angle,count):
    import io
    from blade_designer.models.parameters import DistributionPoint
    from blade_designer.fileio.turbogrid_export import prepare_turbogrid_export
    p=BladeParameters()
    for side,z in (('hub',0),('shroud',10)):
        setattr(p,side,MeridionalCurveParameters(z,50,90,
            [LineSegmentParameters(20),LineSegmentParameters(10,inlet_turn_deg=angle)],5))
    p.diffuser_profile.thickness.points=[DistributionPoint(0,.1),DistributionPoint(1,.1)]
    p.turbogrid.rotation_axis='Z';p.turbogrid.geometry_unit='MM'
    p.blade_rows=initial_rows(p);p.active_blade_row='row-2'
    _,payload=prepare_turbogrid_export(p)
    for side,name in (('hub',p.turbogrid.hub_curve_filename),('shroud',p.turbogrid.shroud_curve_filename)):
        points=np.loadtxt(io.BytesIO(payload[name]))
        expected=generate_meridional(getattr(p,side)).segments[0].end
        assert points.shape==(count,3)
        if angle is not None:assert np.any(np.max(np.abs(points-[expected.r,0,expected.z]),axis=1)<1e-12)


def test_corner_export_rejects_unmapped_derived_wall():
    from types import SimpleNamespace
    from blade_designer.geometry.meridional_segments import corner_distances
    curve=MeridionalCurveParameters(0,100,0,[LineSegmentParameters(10),LineSegmentParameters(10,inlet_turn_deg=10)])
    geometry=generate_meridional(curve)
    derived=SimpleNamespace(source_m=np.array([0.,20.]),segments=geometry.segments)
    with pytest.raises(ValueError,match='derived wall'):corner_distances(curve,derived)
