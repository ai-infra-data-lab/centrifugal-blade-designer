"""Continuous boundary bounds catch gaps hidden between diagnostic Span rows."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import BSpline
from blade_designer.geometry.boundary_gap import boundary_gap_envelope,role_boundary_gap_envelope
from blade_designer.geometry.contact_sources import surface_fingerprint
from blade_designer.geometry.surface_evaluation import SplineSurface
from blade_designer.geometry.role_seams import SEAMS
from test_surface_envelope import patch,plane
from test_conforming_role_grids import surfaces


def check(a,b,**options):
    return boundary_gap_envelope(a,0,b,0,**{'gap_tolerance_mm':1e-10,**options})


@pytest.mark.parametrize('refinements',[0,1,3])
def test_same_boundary_is_zero_and_preserves_source(refinements):
    a=patch(plane);before=deepcopy(a.across.c)
    r=check(a,a,refinements=refinements)
    assert r['numeric_within_tolerance'] and r['same_float64_boundary_representation']
    assert r['max_upper_mm']==r['sample_max_mm']==0
    assert not r['seam_chart_ready'] and not r['continuous_surface_certified']
    np.testing.assert_array_equal(a.across.c,before)


@pytest.mark.parametrize('first,second',[(1,2),(1,3),(2,3),(3,1),(3,2),(2,1)])
def test_different_span_degrees_are_elevated_without_refitting(first,second):
    a=patch(plane,2,tuple(np.linspace(0,1,first+1)))
    b=patch(plane,2,tuple(np.linspace(0,1,second+1)))
    before=deepcopy((a.across.c,b.across.c));r=check(a,b)
    assert r['numeric_within_tolerance'] and r['span_degrees']==[first,second]
    assert r['max_upper_mm']<1e-12 and not r['same_float64_boundary_representation']
    for old,new in zip(before,(a.across.c,b.across.c)):np.testing.assert_array_equal(old,new)


def test_hidden_cubic_gap_matches_three_old_span_samples_but_stays_unresolved():
    a=patch(plane,2,(0.,.2,.7,1.))
    b=patch(lambda s,t:plane(s,t)+[0,0,.4*s*(s-.5)*(s-1)],2,(0.,.2,.7,1.))
    np.testing.assert_allclose(a.evaluate_grid([0,.5,1],[0]),b.evaluate_grid([0,.5,1],[0]),atol=1e-15)
    coarse=check(a,b,gap_tolerance_mm=.001)
    assert coarse['status']=='UNRESOLVED' and coarse['sample_max_mm']<1e-15
    refined=check(a,b,gap_tolerance_mm=.001,refinements=1)
    assert refined['status']=='GAP_OBSERVED' and refined['sample_max_mm']==pytest.approx(.01875)
    analytic=.4*np.sqrt(3)/36
    for level in range(5):
        r=check(a,b,refinements=level)
        assert r['max_upper_mm']>=analytic-1e-14 and r['sample_max_mm']<=analytic+1e-14
    assert refined['max_upper_mm']<coarse['max_upper_mm']


def test_finite_gap_within_budget_is_not_zero_equality_or_chart_approval():
    a=patch(plane,2,(0.,1.));b=patch(lambda s,t:plane(s,t)+[0,0,.25],2,(0.,1.))
    r=check(a,b,gap_tolerance_mm=.25)
    assert r['max_upper_mm']==.25 and r['numeric_within_tolerance']
    assert not r['same_float64_boundary_representation'] and not r['seam_chart_ready']
    assert check(a,b,gap_tolerance_mm=.249)['status']=='GAP_OBSERVED'


@pytest.mark.parametrize('scale',[.01,1.,100.])
def test_rigid_transform_and_scale_preserve_known_gap_with_different_knots(scale):
    a=patch(plane,2,(0.,.2,.7,1.));b=deepcopy(a);b.across.c+=[1,2,3]
    b.across=b.across.insert_knot(.37)
    q,_=np.linalg.qr(np.array([[1.,2,3],[-2,3,1],[3,1,-2]]))
    for s in (a,b):s.across.c=s.across.c@q*scale+[20,-30,50]
    r=check(a,b,gap_tolerance_mm=4*scale,refinements=1,span_range=(.1,.8))
    assert r['numeric_within_tolerance']
    assert r['max_upper_mm']==pytest.approx(np.sqrt(14)*scale,rel=1e-10)
    assert r['span_range']==[.1,.8]


def test_wrong_end_and_reversed_span_are_not_automatically_repaired():
    a=patch(plane,2,(0.,1.));b=patch(lambda s,t:plane(1-s,t),2,(0.,1.))
    assert check(a,b)['status']=='GAP_OBSERVED'
    r=boundary_gap_envelope(a,0,a,-1,gap_tolerance_mm=.01)
    assert r['max_upper_mm']==1 and r['status']=='GAP_OBSERVED'


def test_c0_boundary_curve_is_allowed_without_smoothing():
    along=BSpline([0,0,1,1],np.zeros((2,2,3)),1,axis=1)
    coefficients=np.array([[[0.,0,0],[1,0,0]],[[0,.5,0],[1,.5,0]],[[0,1,1],[1,1,1]]])
    across=BSpline([0,0,.5,1,1],np.moveaxis(coefficients,0,1),1,axis=1)
    a=SplineSurface(along,across);r=check(a,a)
    assert r['numeric_within_tolerance'] and r['required_intervals']==2


def test_discontinuous_span_curve_is_rejected():
    along=BSpline([0,0,1,1],np.zeros((2,2,3)),1,axis=1)
    across=BSpline([0,0,.5,.5,1,1],np.zeros((2,4,3)),1,axis=1)
    with pytest.raises(ValueError,match='Discontinuous'):check(SplineSurface(along,across),patch(plane))


def test_all_declared_role_seams_and_source_identities_are_preserved():
    source=surfaces();before={r:surface_fingerprint(s) for r,s in source.items()}
    result=role_boundary_gap_envelope(source,gap_tolerance_mm=1e-10)
    assert result['all_seams_within_tolerance'] and result['scan_complete']
    assert [(s['first_role'],s['first_end'],s['second_role'],s['second_end']) for s in result['seams']]==list(SEAMS)
    assert result['source_fingerprints']==before=={r:surface_fingerprint(s) for r,s in source.items()}
    assert not result['source_coordinates_modified'] and not result['seam_chart_ready']


def test_role_gap_and_resource_limit_are_propagated_without_partial_success():
    source=surfaces();source['ss'].across.c[1,:,2]+=.02
    result=role_boundary_gap_envelope(source,gap_tolerance_mm=.001)
    assert result['status']=='GAP_OBSERVED' and not result['all_seams_within_tolerance']
    capped=role_boundary_gap_envelope(source,gap_tolerance_mm=.001,refinements=1,max_intervals=1)
    assert capped['status']=='RESOURCE_LIMIT' and not capped['scan_complete']
    assert all(s['report']['intervals']==[] for s in capped['seams'])


def test_observed_gap_does_not_hide_other_seams_resource_failure():
    source=surfaces();source['le'].across=source['le'].across.insert_knot(.25)
    source['ss'].across.c[:,:,0]+=.01
    result=role_boundary_gap_envelope(source,gap_tolerance_mm=.001,max_intervals=1)
    assert result['status']=='GAP_OBSERVED' and not result['scan_complete']
    assert not result['all_seams_within_tolerance']
    assert any(s['report']['status']=='RESOURCE_LIMIT' for s in result['seams'])


@pytest.mark.parametrize('options',[{'gap_tolerance_mm':True},{'gap_tolerance_mm':-1},
    {'gap_tolerance_mm':np.nan},{'refinements':True},{'refinements':5},
    {'max_intervals':0},{'max_intervals':False},{'span_range':(0,0)},
    {'span_range':(0,np.inf)},{'span_range':(-.1,1)},{'span_range':(False,True)}])
def test_invalid_options_rejected(options):
    a=patch(plane)
    with pytest.raises(ValueError):check(a,a,**options)


@pytest.mark.parametrize('end',[True,1,None])
def test_invalid_boundary_end_rejected(end):
    a=patch(plane)
    with pytest.raises(ValueError):boundary_gap_envelope(a,end,a,0,gap_tolerance_mm=0)


def test_missing_roles_and_unsupported_surface_rejected():
    with pytest.raises(ValueError):role_boundary_gap_envelope({},gap_tolerance_mm=0)
    with pytest.raises(ValueError):check(None,patch(plane))
