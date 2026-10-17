"""Independent splitter uses the same PCHIP on its displayed control domain."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import PchipInterpolator
from blade_designer.models.parameters import DistributionPoint,SplitterParameters
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.fileio.project_io import save_project,load_project
from test_impeller_te_rake import radial_parameters


@pytest.mark.parametrize('kind',['blade_angle','thickness'])
@pytest.mark.parametrize('count',[2,4])
def test_visible_controls_match_pchip_and_hidden_upstream_values_do_not_affect_geometry(kind,count,tmp_path):
    p=radial_parameters();p.splitter=SplitterParameters(.35,.65,.5,1.3,deepcopy(p.sections))
    for s in p.splitter.sections:
        start=(1-s.span)*.35+s.span*.65
        nodes=start+(1-start)*np.linspace(0,1,count)
        values=np.array([20.,35.] if count==2 else [20.,36.,24.,35.])
        if kind=='thickness':values/=10
        getattr(s,kind).points=[DistributionPoint(0,5.),DistributionPoint(start/2,6.),
                               *[DistributionPoint(float(x),float(y)) for x,y in zip(nodes,values)]]
    before=deepcopy(p);g=generate_impeller(p)
    for profile,section in zip(p.splitter.sections,g.splitter_sections):
        start=(1-profile.span)*.35+profile.span*.65
        visible=[point for point in getattr(profile,kind).points if point.m_norm>=start]
        x=np.array([point.m_norm for point in visible]);y=np.array([point.value for point in visible])
        query=start+(1-start)*section.camber.m_blade_norm
        actual=section.beta_m_deg if kind=='blade_angle' else section.thickness/1.3
        np.testing.assert_allclose(actual,PchipInterpolator(x,y)(query),atol=1e-12)
        if count==2:np.testing.assert_allclose(actual,np.interp(query,x,y),atol=1e-12)
    assert p==before
    for s in p.splitter.sections:
        getattr(s,kind).points[0].value=30.
        getattr(s,kind).points[1].value=40.
    changed=generate_impeller(p)
    for a,b in zip(g.sections+g.splitter_sections,changed.sections+changed.splitter_sections):
        np.testing.assert_array_equal(a.master_ps.xyz,b.master_ps.xyz)
        np.testing.assert_array_equal(a.master_ss.xyz,b.master_ss.xyz)
    path=tmp_path/'local.json';save_project(path,p);loaded=load_project(path)
    assert loaded==p
    for a,b in zip(changed.splitter_sections,generate_impeller(loaded).splitter_sections):
        np.testing.assert_array_equal(a.master_ps.xyz,b.master_ps.xyz)


@pytest.mark.parametrize('kind',['blade_angle','thickness'])
def test_missing_le_is_seeded_once_from_stored_curve_then_visible_two_points_are_linear(kind):
    p=radial_parameters();p.splitter=SplitterParameters(sections=deepcopy(p.sections))
    for s in p.splitter.sections:
        getattr(s,kind).points=[DistributionPoint(0,4.),DistributionPoint(.4,6.),DistributionPoint(1,3.7)]
    g=generate_impeller(p)
    le=float(PchipInterpolator([0,.4,1],[4,6,3.7])(.5))
    for section in g.splitter_sections:
        actual=section.beta_m_deg if kind=='blade_angle' else section.thickness
        np.testing.assert_allclose(actual,np.linspace(le,3.7,len(actual)),atol=1e-12)
