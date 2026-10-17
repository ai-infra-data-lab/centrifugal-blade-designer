"""Analytic trim contracts, retained source geometry and protected exports."""
from copy import deepcopy
import json
import numpy as np
import pytest
from blade_designer.models.parameters import (BladeParameters,ImpellerTrimParameters,
    TipClearanceParameters,SplitterParameters,RotationDirection)
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.geometry.impeller_trim import area_fraction,_casing
from blade_designer.geometry.flow_area import calculate_flow_area,crossflow_pair
from blade_designer.geometry.flow_path import sample_mean_line
from blade_designer.geometry.meridional_segments import sample_meridional
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid
from test_tip_clearance import axial_parameters
from test_cylindrical_cutoff import radial_parameters


@pytest.mark.parametrize('cut',[0,1,10,45,90])
def test_area_root_matches_axial_annulus_and_radial_width(cut):
    f=area_fraction(50.,70.,20.,1-cut/100)
    assert (50+20*f)**2-50**2==pytest.approx((1-cut/100)*(70**2-50**2),rel=1e-13)
    assert area_fraction(80.,80.,10.,1-cut/100)==pytest.approx(1-cut/100)


@pytest.mark.parametrize('factory',[axial_parameters,radial_parameters,BladeParameters])
def test_area_cut_uses_original_normals_and_preserves_source(factory):
    p=factory();base=generate_impeller(p);original=deepcopy(p)
    p.impeller_trim=ImpellerTrimParameters(10);before=deepcopy(p);g=generate_impeller(p)
    assert calculate_flow_area(g.hub,g.shroud,points=31,strict=False).stations
    assert p==before
    assert p.sections==original.sections and p.hub==original.hub and p.shroud==original.shroud
    for name in ('camber','master_ps','master_ss','master_le','master_te'):
        np.testing.assert_array_equal(getattr(g.sections[0],name).xyz,getattr(base.sections[0],name).xyz)
    positions=np.linspace(.02,.98,37)
    u,means,tangents,_=sample_mean_line(base.hub,base.shroud,positions)
    for x,m,t in zip(u,means,tangents):
        h,s=crossflow_pair(base.hub,base.shroud,m,t,
            sample_meridional(base.hub,x*base.hub.length),sample_meridional(base.shroud,x*base.shroud.length))
        hn,sn=crossflow_pair(g.hub,g.shroud,m,t,h,s)
        ratio=(hn[1]+sn[1])*np.linalg.norm(sn-hn)/((h[1]+s[1])*np.linalg.norm(s-h))
        assert ratio==pytest.approx(.9,abs=2e-5)


@pytest.mark.parametrize('mode,value',[('diameter',216.),('percent',10.)])
@pytest.mark.parametrize('rotation',list(RotationDirection))
def test_od_is_a_cylinder_and_retains_original_side_vertices(mode,value,rotation):
    p=radial_parameters();p.rotation_direction=rotation
    base=generate_impeller(p)
    p.impeller_trim=ImpellerTrimParameters(diameter_mode=mode,
        diameter_mm=value if mode=='diameter' else 0,diameter_cut_percent=value if mode=='percent' else 0)
    before=deepcopy(p);g=generate_impeller(p);assert p==before
    for section,original in zip(g.sections,base.sections):
        np.testing.assert_allclose(section.master_te.r,108.,atol=1e-12)
        for name in ('master_ps','master_ss','camber'):
            c=getattr(section,name);old=getattr(original,name)
            np.testing.assert_array_equal(c.xyz[:-1],old.xyz[:len(c.r)-1])
            assert c.m_blade_norm[-1]<old.m_blade_norm[-1]
        np.testing.assert_array_equal(section.master_le.xyz,original.master_le.xyz)


@pytest.mark.parametrize('rake',[None,12.])
@pytest.mark.parametrize('independent',[False,True])
def test_combined_cut_clearance_splitter_and_rake(rake,independent):
    p=radial_parameters();p.tip_clearance=TipClearanceParameters(.4,.8)
    p.splitter=SplitterParameters(sections=deepcopy(p.sections) if independent else None)
    p.impeller_te_rake_deg=rake;p.impeller_trim=ImpellerTrimParameters(10,'percent',0,5)
    original=deepcopy(p);g=generate_impeller(p);assert p==original
    assert g.trim_report['base_diameter_mm']==pytest.approx(240.)
    for section in (*g.sections,*g.splitter_sections):
        np.testing.assert_allclose(section.master_te.r,114.,atol=1e-12)
    # Radial planes give a 9 mm passage and retain the absolute casing gap.
    np.testing.assert_allclose(g.shroud.z,9.,atol=1e-10)
    expected=9-np.interp(g.sections[-1].camber.r-50,[15,70],[.4,.8])
    np.testing.assert_allclose(g.sections[-1].camber.z,expected,atol=1e-8)


@pytest.mark.parametrize('settings',[None,ImpellerTrimParameters(),ImpellerTrimParameters(diameter_mode='percent')])
def test_disabled_trim_is_identical(settings):
    p=BladeParameters();base=generate_impeller(p);p.impeller_trim=settings;g=generate_impeller(p)
    assert g.source_geometry is None and g.trim_report is None
    for a,b in zip(base.sections,g.sections):
        for name in ('camber','master_ps','master_ss','master_le','master_te'):
            np.testing.assert_array_equal(getattr(a,name).xyz,getattr(b,name).xyz)


def test_axial_clearance_and_passage_use_new_casing():
    from blade_designer.geometry.passage import calculate_passages
    p=axial_parameters();p.tip_clearance=TipClearanceParameters(1,2)
    p.impeller_trim=ImpellerTrimParameters(10);g=generate_impeller(p)
    radius=np.sqrt(50**2+.9*(70**2-50**2))
    np.testing.assert_allclose(g.shroud.r,radius,atol=1e-10)
    np.testing.assert_allclose(g.sections[-1].camber.r[[0,-1]],[radius-1,radius-2],atol=1e-9)
    result=calculate_passages(g,p.geometry.vane_count,points=21)
    assert result.stations and result.throats
    assert result.stations[0].gross_annulus==pytest.approx(.9*np.pi*(70**2-50**2))


@pytest.mark.parametrize('settings',[ImpellerTrimParameters(100),ImpellerTrimParameters(float('nan')),
    ImpellerTrimParameters(-1),ImpellerTrimParameters(diameter_mode='bad'),
    ImpellerTrimParameters(diameter_mode='diameter',diameter_mm=300),
    ImpellerTrimParameters(diameter_mode='percent',diameter_cut_percent=90)])
def test_invalid_trim_does_not_mutate_source(settings):
    p=radial_parameters();p.impeller_trim=settings
    with pytest.raises(ValueError):generate_impeller(p)


def test_excessive_cut_with_gap_is_rejected():
    p=radial_parameters();p.tip_clearance=TipClearanceParameters(4,4)
    p.impeller_trim=ImpellerTrimParameters(90)
    with pytest.raises(ValueError):generate_impeller(p)


def test_json_roundtrip_and_old_json_omits_trim(tmp_path):
    p=radial_parameters();path=tmp_path/'project.json'
    save_project(path,p);assert 'impeller_trim' not in json.loads(path.read_text())
    p.impeller_trim=ImpellerTrimParameters(10,'percent',0,5)
    save_project(path,p);loaded=load_project(path)
    assert loaded==p
    a=generate_impeller(p);b=generate_impeller(loaded)
    np.testing.assert_array_equal(a.sections[-1].master_ps.xyz,b.sections[-1].master_ps.xyz)


def test_output_guard_preserves_existing_files_and_cad_directory(tmp_path):
    from blade_designer.cad.client import prepare_job
    p=radial_parameters();p.impeller_trim=ImpellerTrimParameters(10)
    output=tmp_path/'case';output.mkdir();sentinel=output/'profile.curve';sentinel.write_bytes(b'original')
    with pytest.raises(ValueError,match='trim'):export_turbogrid(output,p)
    assert list(output.iterdir())==[sentinel] and sentinel.read_bytes()==b'original'
    job=tmp_path/'cad'
    with pytest.raises(ValueError,match='trim'):prepare_job(p,job_directory=job)
    assert not job.exists()


def test_diffuser_shape_does_not_change():
    p=radial_parameters();before=generate_diffuser_3d(p)
    p.impeller_trim=ImpellerTrimParameters(15);after=generate_diffuser_3d(p)
    for a,b in zip(before.sections,after.sections):np.testing.assert_array_equal(a.master_ps.xyz,b.master_ps.xyz)


def test_zero_cut_preserves_turbogrid_bytes(tmp_path):
    p=radial_parameters();a=tmp_path/'base';b=tmp_path/'zero'
    export_turbogrid(a,p);p.impeller_trim=ImpellerTrimParameters();export_turbogrid(b,p)
    assert {f.name:f.read_bytes() for f in a.iterdir()}=={f.name:f.read_bytes() for f in b.iterdir()}


def test_owned_shroud_chunks_retain_source_domain():
    from blade_designer.geometry.row_domain import preview_wall_chunks
    p=BladeParameters();p.hub.segments[1].blade_row='rotor';p.shroud.segments[1].blade_row='rotor'
    p.impeller_trim=ImpellerTrimParameters(10);g=generate_impeller(p)
    chunks=preview_wall_chunks(p,g,'rotor')
    start,end=np.interp(g.shroud.source_boundaries[[1,2]],g.shroud.source_m,g.shroud.m)
    actual=np.column_stack((chunks['shroud'][0].z,chunks['shroud'][0].r))
    np.testing.assert_allclose(actual[[0,-1]],sample_meridional(g.shroud,[start,end]))


def test_cut_coincident_with_existing_source_span():
    p=radial_parameters();base=generate_impeller(p)
    p.impeller_trim=ImpellerTrimParameters(50);g=generate_impeller(p)
    np.testing.assert_allclose(g.sections[-1].camber.xyz,base.sections[1].camber.xyz,atol=1e-9)
    np.testing.assert_allclose(g.sections[-1].camber.source_span,.5,atol=1e-10)


def test_source_span_and_distribution_metadata_follow_cut():
    p=radial_parameters()
    for i,profile in enumerate(p.sections):
        for point in profile.blade_angle.points:point.value=10+20*i
        for point in profile.thickness.points:point.value=2+2*i
    p.impeller_trim=ImpellerTrimParameters(10);g=generate_impeller(p)
    np.testing.assert_allclose(g.sections[-1].camber.source_span,.9,atol=1e-10)
    np.testing.assert_allclose(g.sections[-1].beta_m_deg,46.,atol=1e-9)
    np.testing.assert_allclose(g.sections[-1].thickness,5.6,atol=1e-9)
