"""Analytic linked splitter and legacy geometry/serialization protection."""
from copy import deepcopy
from dataclasses import replace
import numpy as np
import pytest
from blade_designer.models.parameters import SplitterParameters,RotationDirection,EdgeType,DistributionPoint
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.geometry.distributions import interpolate_beta_m_deg
from blade_designer.geometry.thickness import generate_thickness
from blade_designer.geometry.impeller_parameter_mapper import measure_te_rake
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid
from test_impeller_te_rake import radial_parameters


@pytest.mark.parametrize('direction',list(RotationDirection))
@pytest.mark.parametrize('edge',list(EdgeType))
@pytest.mark.parametrize('rake',[None,20.])
def test_linked_splitter_preserves_main_and_has_analytic_wrap(direction,edge,rake):
    p=radial_parameters(edge);p.rotation_direction=direction;p.impeller_te_rake_deg=rake
    baseline=generate_impeller(p);p.splitter=SplitterParameters(.35,.65,.4,.7);before=deepcopy(p)
    g=generate_impeller(p)
    assert p==before and len(g.splitter_sections)==len(g.sections)
    offset=direction.sign*2*np.pi/p.geometry.vane_count*.4
    for profile,main,split,original in zip(p.sections,g.sections,g.splitter_sections,baseline.sections):
        for name in ('camber','ps','ss','le','te','master_le','master_ps','master_te','master_ss'):
            np.testing.assert_array_equal(getattr(main,name).xyz,getattr(original,name).xyz)
        start=.35*(1-profile.span)+.65*profile.span
        assert split.m[0]==pytest.approx(main.m[0]+start*(main.m[-1]-main.m[0]))
        assert split.m[-1]==pytest.approx(main.m[-1])
        assert split.camber.theta_rad[-1]==pytest.approx(main.camber.theta_rad[-1]+offset,abs=1e-12)
        source=start+(1-start)*split.camber.m_blade_norm
        np.testing.assert_allclose(split.beta_m_deg,interpolate_beta_m_deg(source,profile.blade_angle.points))
        np.testing.assert_allclose(split.thickness,.7*generate_thickness(source,profile.thickness))
        beta=np.deg2rad(20+20*profile.span)
        expected=direction.sign*np.tan(beta)*np.log(split.camber.r[-1]/split.camber.r[0])
        assert split.camber.theta_rad[-1]-split.camber.theta_rad[0]==pytest.approx(expected,abs=2e-6)
        np.testing.assert_allclose(split.camber.z,main.camber.z[0],atol=1e-10)
        if edge==EdgeType.CUTOFF:np.testing.assert_array_equal(split.te.r,np.full(len(split.te.r),120.))
    if rake is not None:assert measure_te_rake(replace(g,sections=g.splitter_sections))==pytest.approx(rake,abs=1e-7)


def test_varying_distributions_use_original_chord_coordinates_and_json_precision(tmp_path):
    p=radial_parameters()
    for s in p.sections:s.blade_angle.points=[DistributionPoint(0,15),DistributionPoint(.4,35),DistributionPoint(1,20)]
    p.splitter=SplitterParameters(.234567890123456,.654321098765432,.456789012345678,.987654321098765)
    g=generate_impeller(p)
    for profile,split in zip(p.sections,g.splitter_sections):
        f=(1-profile.span)*p.splitter.hub_start_fraction+profile.span*p.splitter.tip_start_fraction
        expected=interpolate_beta_m_deg(f+(1-f)*split.camber.m_blade_norm,profile.blade_angle.points)
        np.testing.assert_array_equal(split.beta_m_deg,expected)
    path=tmp_path/'splitter.json';save_project(path,p);assert load_project(path)==p
    for a,b in zip(g.splitter_sections,generate_impeller(load_project(path)).splitter_sections):
        np.testing.assert_array_equal(a.ps.xyz,b.ps.xyz)


@pytest.mark.parametrize('name,value',[("hub_start_fraction",0),("hub_start_fraction",1),
    ("tip_start_fraction",float('nan')),("pitch_fraction",True),("pitch_fraction",-1),
    ("thickness_scale",0),("thickness_scale",float('inf'))])
def test_invalid_splitter_rejected_before_save(name,value,tmp_path):
    p=radial_parameters();path=tmp_path/'project.json';save_project(path,p);before=path.read_bytes()
    p.splitter=SplitterParameters();setattr(p.splitter,name,value)
    with pytest.raises(ValueError,match='Splitter'):generate_impeller(p)
    with pytest.raises(ValueError,match='Splitter'):save_project(path,p)
    assert path.read_bytes()==before


def test_disabled_json_unchanged_stator_unaffected_and_export_is_protected(tmp_path):
    p=radial_parameters();path=tmp_path/'old.json';save_project(path,p)
    assert '"splitter"' not in path.read_text()
    files=export_turbogrid(tmp_path/'case',p);before={f:f.read_bytes() for f in files}
    static=generate_diffuser_3d(p)
    p.splitter=SplitterParameters();newstatic=generate_diffuser_3d(p)
    assert newstatic.splitter_sections is None
    for a,b in zip(static.sections,newstatic.sections):np.testing.assert_array_equal(a.ps.xyz,b.ps.xyz)
    for destination in (tmp_path/'case',tmp_path/'new'):
        exported=export_turbogrid(destination,p)
        assert len(exported)==4
        assert exported[2].read_text().count('## ')==2
        assert 'Number of Blades Per Set: 2' in exported[3].read_text()
    assert all(f.read_bytes()==before[f] for f in files[:2])


def test_independent_distributions_copy_controls_then_use_visible_domain_without_affecting_main(tmp_path):
    p=radial_parameters();p.impeller_te_rake_deg=20;p.splitter=SplitterParameters()
    linked=generate_impeller(p);p.splitter.sections=deepcopy(p.sections)
    copied=generate_impeller(p)
    assert p.splitter.sections==p.sections
    for main,old,profile,split in zip(copied.sections,linked.sections,p.sections,copied.splitter_sections):
        np.testing.assert_array_equal(main.ps.xyz,old.ps.xyz)
        start=.5
        le=float(generate_thickness(np.array([start]),profile.thickness)[0])
        # The copied peak is upstream of LE: two visible controls interpolate
        # linearly, even though the original complete profile was curved.
        np.testing.assert_allclose(split.thickness,np.linspace(le,profile.thickness.points[-1].value,len(split.thickness)),atol=1e-12)
    for profile in p.splitter.sections:
        for point in profile.blade_angle.points:point.value=10+10*profile.span
        for point in profile.thickness.points:point.value=.8
    changed=generate_impeller(p)
    for main,old,split in zip(changed.sections,linked.sections,changed.splitter_sections):
        np.testing.assert_array_equal(main.ps.xyz,old.ps.xyz)
        np.testing.assert_allclose(split.beta_m_deg,10+10*split.span)
        np.testing.assert_allclose(split.thickness,.8)
        assert split.camber.theta_rad[-1]==pytest.approx(main.camber.theta_rad[-1]+np.pi/p.geometry.vane_count)
    path=tmp_path/'independent.json';save_project(path,p);assert load_project(path)==p
    for a,b in zip(changed.splitter_sections,generate_impeller(load_project(path)).splitter_sections):np.testing.assert_array_equal(a.ps.xyz,b.ps.xyz)
    for profile in p.sections:
        for point in profile.blade_angle.points:point.value=45
        for point in profile.thickness.points:point.value=1.2
    independent=generate_impeller(p)
    for split in independent.splitter_sections:
        np.testing.assert_allclose(split.beta_m_deg,10+10*split.span)
        np.testing.assert_allclose(split.thickness,.8)
    p.sections.insert(1,deepcopy(p.sections[0]));p.sections[1].span=.25
    extra=generate_impeller(p).splitter_sections[1]
    np.testing.assert_allclose(extra.beta_m_deg,12.5)


@pytest.mark.parametrize('profiles',[[],[None]])
def test_invalid_independent_profiles_are_rejected(profiles):
    p=radial_parameters();p.splitter=SplitterParameters(sections=profiles)
    with pytest.raises(ValueError,match='Splitter'):generate_impeller(p)
