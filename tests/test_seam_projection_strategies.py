"""An unequal-speed kink defeats a weighted mean, not the source geometry."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.seam_injectivity import seam_projection_injectivity
from blade_designer.geometry.seam_contact_refinement import subdivide_seam_neighborhood,local_seam_pair_injectivity
from test_seam_injectivity import bezier,strips
from test_seam_contact_refinement import fixture,shear


def kink(speed=.1):
    a=bezier([[[0,0,0],[-speed,0,0]],[[0,1,0],[-speed,1,0]]])
    b=bezier([[[0,0,0],[-.8,0,.6]],[[0,1,0],[-.8,1,.6]]])
    return a,b


def check(a,b,**options):
    return seam_projection_injectivity(a,0,b,0,**{'first_width':1.,'second_width':1.,
        'reference_min_mm':1e-12,'monotonic_margin':0.,'projection_strategy':'balanced_transverse',**options})


@pytest.mark.parametrize('speed',[.05,.1,.2])
@pytest.mark.parametrize('refinements',[0,2])
def test_unequal_speed_kink_has_independent_analytic_positive_bound(speed,refinements):
    a,b=kink(speed);before=deepcopy((a.across.c,b.across.c))
    legacy=check(a,b,projection_strategy='average')
    assert not legacy['numeric_injective'] and legacy['min_symmetric_lower']<0
    r=check(a,b,refinements=refinements)
    assert r['numeric_injective'] and r['min_symmetric_lower']==pytest.approx(2*speed/(1+speed))
    assert r['widths']==[1,1] and len(r['cells'])==2*4**refinements
    # Each original derivative is checked; balancing does NOT normalize the source speed.
    expected=[2*speed/(1+speed),2/(1+speed)]
    projection=np.array(r['projection'])
    for side,derivative in enumerate((np.array([[0,speed],[1,0],[0,0]]),np.array([[0,-.8],[1,0],[0,.6]]))):
        matrix=projection@derivative
        np.testing.assert_allclose(matrix,np.diag([1,expected[side]]),atol=1e-12)
    for s,old in zip((a,b),before):np.testing.assert_array_equal(s.across.c,old)
    assert not r['roundoff_certified'] and not r['whole_geometry_verified']


@pytest.mark.parametrize('scale',[.01,1.,100.])
def test_rigid_transform_scale_does_not_change_analytic_condition(scale):
    a,b=kink();q,_=np.linalg.qr(np.array([[1.,2,3],[-2,3,1],[3,1,-2]]))
    for s in (a,b):s.across.c=s.across.c@q*scale+[10,-20,30]
    r=check(a,b)
    assert r['numeric_injective'] and r['min_symmetric_lower']==pytest.approx(2/11,abs=1e-10)


def test_unspecified_strategy_is_identical_to_explicit_historical_average():
    a,b=kink();options=dict(first_width=1.,second_width=1.,reference_min_mm=1e-12,monotonic_margin=0.)
    implicit=seam_projection_injectivity(a,0,b,0,**options)
    explicit=seam_projection_injectivity(a,0,b,0,projection_strategy='average',**options)
    assert implicit==explicit and not implicit['numeric_injective']


@pytest.mark.parametrize('strategy',[None,True,1,[],{},'auto','balanced'])
def test_unknown_strategies_are_rejected(strategy):
    with pytest.raises(ValueError,match='projection_strategy'):check(*strips(),projection_strategy=strategy)


def test_zero_transverse_is_unresolved_without_normalization_or_geometry_repair():
    a,b=kink(0)
    r=check(a,b)
    assert r['reason']=='reference_transverse' and not r['numeric_injective']
    assert r['projection'] is None and not r['cells']


def test_transverse_threshold_and_monotonic_margin_remain_strict():
    a,b=kink(.1)
    assert check(a,b,reference_min_mm=.1)['reason']=='reference_transverse'
    assert not check(a,b,monotonic_margin=1.)['numeric_injective']


def test_opposite_directions_overlapping_sides_do_not_get_a_positive_projection():
    a,_=strips()
    r=check(a,a)
    assert r['reason']=='reference_rank' and not r['numeric_injective']


def test_span_rank_failure_cannot_be_hidden_by_a_nonzero_transverse_direction():
    a,b=kink()
    for s in (a,b):s.across.c[1]=s.across.c[0]
    assert check(a,b)['reason']=='reference_rank'


def test_positive_center_does_not_hide_a_fold_away_from_the_seam():
    a,_=strips()
    b=bezier([[[0,0,0],[.5,0,0],[-1,0,0]],[[0,1,0],[.5,1,0],[-1,1,0]]])
    r=check(a,b,refinements=2)
    assert not r['numeric_injective'] and r['min_symmetric_lower']<0
    assert r['widths']==[1,1]


def test_gap_and_resource_limits_are_preserved_before_projection_selection():
    a,b=kink();b.across.c[:,:,2]+=1e-15
    assert check(a,b)['reason']=='boundary_representation_mismatch'
    r=check(*kink(),max_cells=1)
    assert r['status']=='RESOURCE_LIMIT' and r['projection'] is None and not r['cells']


def test_balanced_strategy_is_propagated_through_subdivision_and_candidate_binding():
    kwargs=dict(reference_min_mm=1e-12,monotonic_margin=0.,projection_strategy='balanced_transverse')
    a,b=shear()
    r=subdivide_seam_neighborhood(a,0,b,0,first_width=1,second_width=1,**kwargs)
    assert r['status']=='LOCAL_CHARTS_ONLY' and not r['numeric_injective']
    assert all(n['report']['projection_strategy']=='balanced_transverse' for n in r['charts'])
    source,envelope=fixture();r=local_seam_pair_injectivity(source,envelope,1,2,**kwargs)
    assert r['expected_parameter_contact_only'] and r['source_identity_checked']
    assert r['neighborhood_report']['root_report']['projection_strategy']=='balanced_transverse'
