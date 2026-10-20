"""Analytic triangle approximation errors and explicit unresolved budgets."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.surface_triangulation import adaptive_triangle_envelope
from test_surface_envelope import patch,plane


def saddle(s,t):return plane(s,t)+np.column_stack((0*t,0*t,s*t))


def test_affine_plane_is_zero_without_refinement_or_source_changes():
    a=patch(plane,2,(0.,1.));before=deepcopy(a.across.c)
    r=adaptive_triangle_envelope(a,target_mm=0)
    assert r['status']=='NUMERIC_TARGET_MET' and r['cell_count']==1
    assert r['max_upper_mm']==r['sample_max_mm']==0
    np.testing.assert_array_equal(a.across.c,before)
    assert not r['contact_ready'] and not r['roundoff_certified']


@pytest.mark.parametrize('depth',[0,1,2,3])
def test_bilinear_saddle_has_known_diagonal_error_and_quarter_convergence(depth):
    a=patch(saddle,2,(0.,1.))
    r=adaptive_triangle_envelope(a,target_mm=0,max_depth=depth,max_cells=1000)
    assert r['cell_count']==4**depth
    assert r['max_upper_mm']==pytest.approx(.25/4**depth,abs=2e-14)
    assert r['sample_max_mm']==pytest.approx(.25/4**depth,abs=2e-14)
    assert r['status']=='UNRESOLVED'


def test_hidden_bump_missed_at_corners_requires_refinement():
    a=patch(lambda s,t:plane(s,t)+np.column_stack((0*t,0*t,16*s*(1-s)*t*(1-t))),3)
    coarse=adaptive_triangle_envelope(a,target_mm=.02,max_depth=0)
    assert coarse['sample_max_mm']==pytest.approx(1.)
    assert coarse['max_upper_mm']>=1
    fine=adaptive_triangle_envelope(a,target_mm=.02,max_depth=6,max_cells=4096)
    assert fine['status']=='NUMERIC_TARGET_MET' and fine['max_upper_mm']<=.02
    assert fine['cell_count']>coarse['cell_count']


def test_resource_budget_retains_complete_domain_as_unresolved_cells():
    a=patch(saddle,2,(0.,1.))
    r=adaptive_triangle_envelope(a,target_mm=1e-6,max_cells=7)
    assert r['cell_count']==7 and r['unresolved_cells']>0
    assert sum((c['span_range'][1]-c['span_range'][0])*(c['xi_range'][1]-c['xi_range'][0])
               for c in r['cells'])==pytest.approx(1.)


@pytest.mark.parametrize('scale',[.01,1.,10.])
def test_translation_rotation_and_scale(scale):
    a=patch(saddle,2,(0.,1.));theta=.7
    rot=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1]])
    a.across.c=a.across.c@rot.T*scale+[20,-3,5]
    r=adaptive_triangle_envelope(a,target_mm=0,max_depth=1)
    assert r['max_upper_mm']==pytest.approx(scale/16,abs=1e-13)


@pytest.mark.parametrize('options',[{'target_mm':True},{'target_mm':-1},{'target_mm':float('nan')},
    {'max_depth':True},{'max_depth':13},{'max_depth':-1},{'max_cells':True},{'max_cells':0}])
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValueError):adaptive_triangle_envelope(patch(plane),**{'target_mm':.01,**options})


def test_initial_budget_and_unsupported_surface_are_rejected():
    with pytest.raises(ValueError,match='Initial'):adaptive_triangle_envelope(patch(plane),target_mm=.01,max_cells=1)
    with pytest.raises(ValueError):adaptive_triangle_envelope(None,target_mm=.01)


def test_dense_independent_saddle_error_is_below_each_cell_envelope():
    r=adaptive_triangle_envelope(patch(saddle,2,(0.,1.)),target_mm=.03)
    for cell in r['cells']:
        u0,u1=cell['span_range'];v0,v1=cell['xi_range']
        # z=uv, T's z differs by the cell twist times min(x,y)*(1-max(x,y)).
        x=np.linspace(0,1,31)[:,None];y=np.linspace(0,1,35)[None,:]
        dense=(u1-u0)*(v1-v0)*np.max(np.minimum(x,y)*(1-np.maximum(x,y)))
        assert dense<=cell['upper_mm']+1e-14


def test_multiple_knots_and_c0_join_keep_original_surface_and_complete_domain():
    from scipy.interpolate import make_interp_spline
    a=patch(plane,3,(0.,.5,1.));a.along=a.along.insert_knot(.5,2)
    a.across=make_interp_spline([0.,.5,1.],a.along.c,k=2,axis=1)
    before=deepcopy((a.along.t,a.across.c))
    r=adaptive_triangle_envelope(a,target_mm=1e-9,max_depth=0)
    assert r['initial_cells']==r['cell_count']==2 and r['status']=='NUMERIC_TARGET_MET'
    np.testing.assert_array_equal(a.along.t,before[0]);np.testing.assert_array_equal(a.across.c,before[1])
    a.along=a.along.insert_knot(.5,1)
    a.across=make_interp_spline([0.,.5,1.],a.along.c,k=2,axis=1)
    with pytest.raises(ValueError,match='Discontinuous'):adaptive_triangle_envelope(a,target_mm=1)


def test_reasons_and_nonfinite_coefficients_are_explicit():
    a=patch(saddle,2,(0.,1.))
    assert {c['reason'] for c in adaptive_triangle_envelope(a,target_mm=0,max_depth=0)['cells']}=={'max_depth'}
    assert {c['reason'] for c in adaptive_triangle_envelope(a,target_mm=0,max_cells=1)['cells']}=={'max_cells'}
    a.across.c[0,0,0]=float('inf')
    with pytest.raises(ValueError):adaptive_triangle_envelope(a,target_mm=1)
