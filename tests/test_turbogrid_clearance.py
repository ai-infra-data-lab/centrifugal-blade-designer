"""Physical Tip retention and analytic spanwise continuation to the casing."""
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from blade_designer.models.parameters import TipClearanceParameters,RotationDirection,EdgeType,SplitterParameters
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.span_extension import extend_tip_to_shroud
from blade_designer.geometry.blade_edge import project_to_wall
from blade_designer.fileio.turbogrid_export import export_turbogrid,closed_profile
from blade_designer.fileio.project_io import load_project
from test_tip_clearance import axial_parameters
from test_impeller_te_rake import radial_parameters
from test_stator_turbogrid_export import profiles


@pytest.mark.parametrize('angle',[0.,35.])
def test_analytic_line_casing_and_unwrapped_spanwise_theta(angle):
    p=axial_parameters();a=np.deg2rad(angle)
    tangent=np.array([np.cos(a),np.sin(a)]);outward=np.array([-tangent[1],tangent[0]])
    p.hub=MeridionalCurveParameters(0,50,angle,[LineSegmentParameters(100)])
    p.shroud=MeridionalCurveParameters(*(np.array([0,50])+20*outward),angle,[LineSegmentParameters(100)])
    p.tip_clearance=TipClearanceParameters(1.,2.);p.impeller_te_rake_deg=20.
    before=deepcopy(p);g=generate_impeller(p);saved=deepcopy(g);outer=extend_tip_to_shroud(g)
    for name in ('camber','ps','ss','le','te','master_ps','master_ss','master_le','master_te'):
        h,t,e=(getattr(s,name) for s in (g.sections[-2],g.sections[-1],outer))
        tip=np.column_stack((t.z,t.r));delta=tip-np.column_stack((h.z,h.r))
        expected_fraction=((np.array([p.shroud.start_z,p.shroud.start_r])-tip)@outward)/(delta@outward)
        expected=tip+expected_fraction[:,None]*delta
        np.testing.assert_allclose(np.column_stack((e.z,e.r)),expected,atol=1e-11)
        np.testing.assert_allclose(e.theta_rad,t.theta_rad+expected_fraction*(t.theta_rad-h.theta_rad),atol=1e-13)
        np.testing.assert_allclose((np.column_stack((e.z,e.r))-np.array([p.shroud.start_z,p.shroud.start_r]))@outward,0,atol=1e-11)
    for original,current in zip(saved.sections,g.sections):
        for name in ('camber','ps','ss','le','te','master_ps','master_ss','master_le','master_te'):
            np.testing.assert_array_equal(getattr(original,name).xyz,getattr(current,name).xyz)
    assert p==before


@pytest.mark.parametrize('direction',list(RotationDirection))
@pytest.mark.parametrize('rake',[None,25.])
def test_radial_cutoff_extension_remains_constant_d_and_preserves_rake_tip(direction,rake):
    p=radial_parameters(EdgeType.CUTOFF);p.rotation_direction=direction;p.impeller_te_rake_deg=rake
    p.tip_clearance=TipClearanceParameters(.5,1.)
    g=generate_impeller(p);outer=extend_tip_to_shroud(g)
    np.testing.assert_allclose(outer.master_te.r,120,atol=1e-10)
    np.testing.assert_allclose(outer.master_te.z,20,atol=1e-10)
    previous,tip=(s.master_te for s in g.sections[-2:])
    fraction=(20-tip.z)/(tip.z-previous.z)
    np.testing.assert_allclose(outer.master_te.theta_rad,tip.theta_rad+fraction*(tip.theta_rad-previous.theta_rad),atol=1e-13)


@pytest.mark.parametrize('axis,order,unit,scale',[
    ('Z',[0,1,2],'MM',1.),('X',[2,0,1],'CM',.1),('Y',[1,2,0],'M',.001)])
def test_export_keeps_actual_sections_and_adds_shroud_last(tmp_path,axis,order,unit,scale):
    p=radial_parameters();p.tip_clearance=TipClearanceParameters(.5,1.)
    p.turbogrid.rotation_axis=axis;p.turbogrid.geometry_unit=unit;p.export.significant_digits=15
    before=deepcopy(p);g=generate_impeller(p);outer=extend_tip_to_shroud(g)
    files=export_turbogrid(tmp_path,p);actual=profiles(files[2])
    assert len(files)==4 and len(actual)==len(g.sections)+1
    assert [v[0] for v in actual]==['# Hub','# Span_0.5','# Tip_clearance','# Shroud_extension']
    for (_,xyz,markers),s in zip(actual,[*g.sections,outer]):
        expected,expected_markers=closed_profile(s)
        np.testing.assert_allclose(xyz,expected[:,order]*scale,rtol=6e-15,atol=1e-12*scale)
        np.testing.assert_array_equal(xyz[0],xyz[-1])
        assert markers==expected_markers and sorted(markers.values())==['le','te']
        assert np.all(np.linalg.norm(np.diff(xyz,axis=0),axis=1)>0)
    inf=files[3].read_text()
    assert '! Physical Tip: Profile Number 3' in inf
    assert f'Geometry Units: {unit}' in inf and f'Axis of Rotation: {axis}' in inf
    assert p==before


@pytest.mark.parametrize('le,te',[(.5,1.),(0.,1.),(1.,0.)])
def test_curved_packaged_default_has_exact_casing_extension_and_unchanged_display_tip(tmp_path,le,te):
    from blade_designer.models.blade_rows import row_parameters
    project=load_project(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json')
    p=row_parameters(project,project.blade_rows[0]);p.blade_rows=deepcopy(project.blade_rows)
    p.active_blade_row='row-1';p.tip_clearance=TipClearanceParameters(le,te)
    p.blade_rows[0].parameters.tip_clearance=deepcopy(p.tip_clearance)
    # This test isolates casing extension. The new user template has a
    # splitter, whose unsupported TurboGrid path is tested separately.
    p.splitter=None;p.blade_rows[0].parameters.splitter=None
    # Use a complete export domain on this disposable default-model copy.
    for wall in (p.hub,p.shroud):
        for segment in wall.segments:segment.blade_row='row-1'
    p.export.significant_digits=15;g=generate_impeller(p);extended=extend_tip_to_shroud(g)
    for curve in (extended.le,extended.ps,extended.te,extended.ss):
        for point in np.column_stack((curve.z,curve.r)):
            _,foot=project_to_wall(g.shroud,point)
            np.testing.assert_allclose(point,foot,atol=1e-8)
    output=profiles(export_turbogrid(tmp_path,p)[2])
    expected,markers=closed_profile(g.sections[-1])
    np.testing.assert_allclose(output[-2][1],expected,rtol=6e-15,atol=1e-12)
    assert output[-2][2]==markers


@pytest.mark.parametrize('invalid',['gap','width','precision','filename','domain','snapshot','splitter'])
def test_invalid_clearance_export_preserves_existing_case_and_does_not_create_new(tmp_path,invalid):
    p=axial_parameters();p.tip_clearance=TipClearanceParameters(1.,2.)
    case=tmp_path/'case';files=export_turbogrid(case,p);saved={f.name:f.read_bytes() for f in files}
    if invalid=='gap':p.tip_clearance.le_mm=-1
    elif invalid=='width':p.tip_clearance.te_mm=20
    elif invalid=='precision':p.export.significant_digits=1
    elif invalid=='filename':p.turbogrid.profile_curve_filename='../escape.curve'
    elif invalid=='splitter':p.splitter=SplitterParameters()
    elif invalid=='snapshot':
        from blade_designer.models.blade_rows import initial_rows
        p.blade_rows=initial_rows(p);p.active_blade_row='row-1';p.tip_clearance=None
    else:
        from blade_designer.models.blade_rows import initial_rows
        p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
        p.hub.segments[0].blade_row='row-1';p.shroud.segments[0].blade_row='row-2'
    for destination in (case,tmp_path/'new'):
        with pytest.raises(ValueError):export_turbogrid(destination,p)
    assert {f.name:f.read_bytes() for f in case.iterdir()}==saved
    assert not (tmp_path/'new').exists()


@pytest.mark.parametrize('invalid',['collapsed','away','nan'])
def test_invalid_span_extension_rejected(invalid):
    p=axial_parameters();p.tip_clearance=TipClearanceParameters(1.,2.);g=generate_impeller(p)
    previous,tip=(s.camber for s in g.sections)
    if invalid=='collapsed':previous.r[:]=tip.r;previous.z[:]=tip.z
    elif invalid=='away':previous.r[:]=tip.r+1.
    else:tip.r[0]=float('nan')
    with pytest.raises(ValueError,match='Span extension'):extend_tip_to_shroud(g)
