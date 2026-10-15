"""Analytic TE chord rake and beta-preserving stacking, independent of Qt."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import (BladeParameters,BladeSection,BladeAngleParameters,
    DistributionPoint,EdgeType,RotationDirection)
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.geometry.impeller_parameter_mapper import measure_te_rake
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid


def radial_parameters(edge=EdgeType.CUTOFF):
    p=BladeParameters()
    p.hub=MeridionalCurveParameters(0,50,90,[LineSegmentParameters(100)])
    p.shroud=MeridionalCurveParameters(20,50,90,[LineSegmentParameters(100)])
    p.impeller_edges.trailing_edge.hub_m_flow_norm=.7
    p.impeller_edges.trailing_edge.shroud_m_flow_norm=.85
    p.sections.insert(1,BladeSection(.5))
    p.geometry.theta_le_deg=5
    for s in p.sections:
        s.edge_parameters.te_type=edge
        s.blade_angle=BladeAngleParameters([DistributionPoint(0,20+20*s.span),DistributionPoint(1,20+20*s.span)])
    # Keep legacy Hub aliases valid when replacing a whole section distribution.
    p.blade_angle=p.sections[0].blade_angle
    return p


@pytest.mark.parametrize('direction',list(RotationDirection))
@pytest.mark.parametrize('target',[-30.,0.,25.])
def test_mapper_meets_analytic_rake_preserves_beta_walls_and_cutoff(direction,target):
    p=radial_parameters();p.rotation_direction=direction
    baseline=generate_impeller(p);p.impeller_te_rake_deg=target;before=deepcopy(p)
    actual=generate_impeller(p)
    assert p==before
    delta=2*np.arcsin(20*np.tan(np.deg2rad(target))/(2*120))
    anchor=baseline.sections[0].camber.theta_rad[-1]
    for base,section in zip(baseline.sections,actual.sections):
        assert section.camber.theta_rad[-1]==pytest.approx(anchor+section.span*delta,abs=1e-12)
        expected_wrap=direction.sign*np.tan(np.deg2rad(20+20*section.span))*np.log(120/section.camber.r[0])
        assert section.camber.theta_rad[-1]-section.camber.theta_rad[0]==pytest.approx(expected_wrap,abs=2e-6)
        np.testing.assert_array_equal(section.beta_m_deg,base.beta_m_deg)
        np.testing.assert_array_equal(section.thickness,base.thickness)
        offset=section.camber.theta_rad[0]-base.camber.theta_rad[0]
        for name in ('camber','le','ps','te','ss','master_le','master_ps','master_te','master_ss'):
            a,b=getattr(section,name),getattr(base,name)
            np.testing.assert_array_equal(a.r,b.r);np.testing.assert_array_equal(a.z,b.z)
            np.testing.assert_allclose(a.theta_rad-b.theta_rad,offset,atol=1e-14)
        np.testing.assert_array_equal(section.te.r,np.full(len(section.te.r),120.))
    np.testing.assert_array_equal(actual.sections[0].camber.xyz,baseline.sections[0].camber.xyz)
    assert measure_te_rake(actual)==pytest.approx(target,abs=1e-8)
    # Independently measure the 3D chord against the midpoint meridional plane.
    h,t=actual.sections[0].camber.xyz[-1],actual.sections[-1].camber.xyz[-1]
    mid=(h+t)/2;normal=np.array([-mid[1],mid[0],0.]);normal/=np.linalg.norm(normal)
    angle=np.rad2deg(np.arcsin(np.dot(t-h,normal)/np.linalg.norm(t-h)))
    assert angle==pytest.approx(target,abs=1e-8)


@pytest.mark.parametrize('edge',list(EdgeType))
def test_all_edge_types_json_and_turbogrid_use_same_mapped_geometry(tmp_path,edge):
    p=radial_parameters(edge);p.impeller_te_rake_deg=15.;p.export.significant_digits=15
    path=tmp_path/'rake.json';save_project(path,p);restored=load_project(path)
    assert restored==p and restored.impeller_te_rake_deg==15
    g=generate_impeller(restored);files=export_turbogrid(tmp_path/'case',restored)
    curves=[]
    for line in files[2].read_text().splitlines():
        if line.startswith('#'):curves.append([])
        else:curves[-1].append([float(v) for v in line.split()[:3]])
    for curve,s in zip(curves,g.sections):
        expected=np.concatenate([s.le.xyz[:-1],s.ps.xyz[:-1],s.te.xyz[:-1],s.ss.xyz[::-1][:-1],s.le.xyz[:1]])
        np.testing.assert_allclose(curve,expected,atol=1e-12)
    assert measure_te_rake(g)==pytest.approx(15.,abs=1e-8)


@pytest.mark.parametrize('target',[90,-90,True,'20',[],float('nan'),float('inf')])
def test_invalid_targets_are_rejected(target):
    p=radial_parameters();p.impeller_te_rake_deg=target
    with pytest.raises(ValueError,match='TE Rake'):generate_impeller(p)


def test_unreachable_target_preserves_project_and_export(tmp_path):
    p=radial_parameters();path=tmp_path/'project.json';save_project(path,p)
    files=export_turbogrid(tmp_path/'case',p);before={f:f.read_bytes() for f in [path,*files]}
    p.impeller_te_rake_deg=89.
    for call in (lambda:save_project(path,p),lambda:export_turbogrid(tmp_path/'case',p),
                 lambda:export_turbogrid(tmp_path/'new',p)):
        with pytest.raises(ValueError,match='unreachable'):call()
    assert all(f.read_bytes()==data for f,data in before.items())
    assert not (tmp_path/'new').exists()


def test_disabled_rake_keeps_legacy_json_and_static_geometry(tmp_path):
    p=BladeParameters();g=generate_diffuser_3d(p)
    path=tmp_path/'legacy.json';save_project(path,p)
    assert 'impeller_te_rake_deg' not in path.read_text()
    assert load_project(path)==p
    p.impeller_te_rake_deg=20
    other=generate_diffuser_3d(p)
    for a,b in zip(g.sections,other.sections):np.testing.assert_array_equal(a.master_ps.xyz,b.master_ps.xyz)
