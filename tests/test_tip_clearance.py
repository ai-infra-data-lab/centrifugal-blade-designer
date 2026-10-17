"""Analytic normal clearance, legacy identity, casing/Tip separation and I/O."""
from copy import deepcopy
import json
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters,TipClearanceParameters,EdgeType,SplitterParameters
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.geometry.blade_edge import project_to_wall
from blade_designer.geometry.passage import calculate_passages
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid


def axial_parameters():
    p=BladeParameters()
    p.hub=MeridionalCurveParameters(0,50,0,[LineSegmentParameters(100)])
    p.shroud=MeridionalCurveParameters(0,70,0,[LineSegmentParameters(100)])
    for profile in p.sections:
        for point in profile.blade_angle.points:point.value=20.
    return p


@pytest.mark.parametrize('le,te',[(1.,2.),(0.,1.),(1.,0.),(.75,.75)])
def test_axial_normal_gap_and_physical_arclength_linear_interpolation(le,te):
    p=axial_parameters();baseline=generate_impeller(p)
    p.tip_clearance=TipClearanceParameters(le,te);before=deepcopy(p)
    g=generate_impeller(p);tip=g.tip
    assert p==before
    expected=np.interp(tip.casing_m,[15,85],[le,te])
    np.testing.assert_allclose(tip.z,tip.casing_m,atol=1e-12)
    np.testing.assert_allclose(tip.r,70-expected,atol=1e-12)
    np.testing.assert_array_equal(tip.clearance_mm,expected)
    for curve in ('camber','master_ps','master_ss','master_le','master_te'):
        np.testing.assert_array_equal(getattr(g.sections[0],curve).xyz,getattr(baseline.sections[0],curve).xyz)
    for index,clearance in ((0,le),(-1,te)):
        assert g.sections[-1].camber.r[index]==pytest.approx(70-clearance,abs=1e-9)
    np.testing.assert_array_equal(g.shroud.r,baseline.shroud.r)
    np.testing.assert_array_equal(g.shroud.z,baseline.shroud.z)


def test_radial_cutoff_uses_actual_te_gap_and_splitter_shares_tip_wall():
    from test_impeller_te_rake import radial_parameters
    p=radial_parameters(EdgeType.CUTOFF);p.tip_clearance=TipClearanceParameters(.5,1.)
    p.splitter=SplitterParameters();g=generate_impeller(p)
    assert g.tip.te_casing_m==pytest.approx(70)
    assert g.sections[-1].camber.z[0]==pytest.approx(19.5)
    assert g.sections[-1].camber.z[-1]==pytest.approx(19.)
    for section in (g.sections[-1],g.splitter_sections[-1]):
        np.testing.assert_allclose(section.master_te.r,120.,atol=1e-12)
        np.testing.assert_allclose(section.master_te.z,19.,atol=1e-9)
        expected=20-np.interp(section.camber.r-50,[15,70],[.5,1.])
        np.testing.assert_allclose(section.camber.z,expected,atol=2e-7)


def test_conical_clearance_moves_both_r_and_z_along_the_normal():
    p=axial_parameters();angle=np.deg2rad(35.)
    tangent=np.array([np.cos(angle),np.sin(angle)]);normal=np.array([-tangent[1],tangent[0]])
    p.hub=MeridionalCurveParameters(0,50,35,[LineSegmentParameters(100)])
    start=np.array([0,50])+20*normal
    p.shroud=MeridionalCurveParameters(*start,35,[LineSegmentParameters(100)])
    p.tip_clearance=TipClearanceParameters(1,2)
    g=generate_impeller(p);tip=g.tip
    expected=start+tip.casing_m[:,None]*tangent-tip.clearance_mm[:,None]*normal
    np.testing.assert_allclose(np.column_stack((tip.z,tip.r)),expected,atol=1e-12)


def test_curved_default_normal_distance_and_no_parameter_mutation():
    from pathlib import Path
    from blade_designer.models.blade_rows import row_parameters
    p=load_project(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json')
    p=row_parameters(p,p.blade_rows[0]);p.tip_clearance=TipClearanceParameters(.5,1.)
    g=generate_impeller(p)
    for index,clearance in ((0,.5),(-1,1.)):
        point=np.array([g.sections[-1].camber.z[index],g.sections[-1].camber.r[index]])
        _,foot=project_to_wall(g.shroud,point)
        assert np.linalg.norm(point-foot)==pytest.approx(clearance,abs=2e-6)
    passage=calculate_passages(g,p.geometry.vane_count)
    assert passage.stations and not passage.errors
    assert all(s.tip_gap_per_pitch>0 for s in passage.stations)


def test_zero_clearance_is_identical_and_stator_does_not_move(tmp_path):
    p=axial_parameters();base=generate_impeller(p);stator=generate_diffuser_3d(p)
    files=export_turbogrid(tmp_path/'old',p);old=[f.read_bytes() for f in files]
    p.tip_clearance=TipClearanceParameters(0,0)
    new=generate_impeller(p);assert new.tip is None
    for a,b in zip(base.sections,new.sections):
        for name in ('camber','master_ps','master_ss','master_le','master_te'):
            np.testing.assert_array_equal(getattr(a,name).xyz,getattr(b,name).xyz)
    assert [f.read_bytes() for f in export_turbogrid(tmp_path/'zero',p)]==old
    p.tip_clearance=TipClearanceParameters(.5,1.)
    actual=generate_diffuser_3d(p);assert actual.tip is None
    for a,b in zip(stator.sections,actual.sections):np.testing.assert_array_equal(a.master_ps.xyz,b.master_ps.xyz)


def test_json_roundtrip_and_failed_export_preserve_existing_files(tmp_path):
    p=axial_parameters();path=tmp_path/'project.json';save_project(path,p)
    assert 'tip_clearance' not in json.loads(path.read_text())
    files=export_turbogrid(tmp_path/'case',p);before={f:f.read_bytes() for f in files}
    p.tip_clearance=TipClearanceParameters(.123456789012345,.987654321098765)
    save_project(path,p);assert load_project(path)==p
    assert json.loads(path.read_text())['schema_version']=='0.4'
    # Positive clearance is now supported in Profile Points. Invalid width
    # must still leave existing output untouched, and CAD remains guarded.
    valid=deepcopy(p);p.tip_clearance.te_mm=20.
    with pytest.raises(ValueError,match='Tip clearance'):
        export_turbogrid(tmp_path/'case',p)
    with pytest.raises(ValueError,match='Tip clearance'):
        export_turbogrid(tmp_path/'new',p)
    assert all(f.read_bytes()==data for f,data in before.items()) and not (tmp_path/'new').exists()
    from blade_designer.cad.client import prepare_job
    with pytest.raises(ValueError,match='Tip clearance TurboGrid CAD'):
        prepare_job(valid,'both',tmp_path/'job')
    assert not (tmp_path/'job').exists()


@pytest.mark.parametrize('value',[-1.,float('nan'),float('inf'),True,'1'])
def test_invalid_clearance_rejected_before_save(value,tmp_path):
    p=axial_parameters();path=tmp_path/'project.json';save_project(path,p);before=path.read_bytes()
    p.tip_clearance=TipClearanceParameters(value,1.)
    with pytest.raises(ValueError,match='Tip clearance'):generate_impeller(p)
    with pytest.raises(ValueError,match='Tip clearance'):save_project(path,p)
    assert path.read_bytes()==before


def test_clearance_cannot_reach_hub():
    p=axial_parameters();p.tip_clearance=TipClearanceParameters(20,20)
    with pytest.raises(ValueError,match='Hub–casing width'):generate_impeller(p)


def test_passage_area_includes_gap_without_growing_blade_height():
    from test_passage import radial
    row=radial(True)
    # A known planar radial case: casing Z=20, Tip Z=18, Hub Z=0.
    for section in (row.sections[-1],row.splitter_sections[-1]):
        for curve in (section.camber,section.master_le,section.master_ps,section.master_te,section.master_ss):curve.z[:]=18.
    for section in (row.sections[1],row.splitter_sections[1]):
        for curve in (section.camber,section.master_le,section.master_ps,section.master_te,section.master_ss):curve.z[:]=9.
    from types import SimpleNamespace
    row.tip=SimpleNamespace()
    result=calculate_passages(row,12)
    assert not result.errors
    for cut in result.stations:
        r=40+70*cut.m_flow_norm;pitch=2*np.pi/12
        assert cut.tip_gap_per_pitch==pytest.approx(pitch*r*2.)
        if cut.main_splitter is not None:
            assert cut.main_splitter+cut.splitter_main+cut.tip_gap_per_pitch==pytest.approx(cut.net_per_pitch)
    assert result.throats[1].strip_area==pytest.approx(result.throats[1].minimum_width*18.)
