"""Analytic adjacent strips and folds; source coordinates must not be repaired."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import BSpline
from blade_designer.geometry.surface_evaluation import SplineSurface
from blade_designer.geometry.seam_injectivity import seam_projection_injectivity
from blade_designer.geometry.surface_injectivity import surface_projection_injectivity


def bezier(net):
    net=np.asarray(net,float);p,q=np.array(net.shape[:2])-1
    along=BSpline([0]*(q+1)+[1]*(q+1),np.zeros((p+1,q+1,3)),int(q),axis=1)
    across=BSpline([0]*(p+1)+[1]*(p+1),np.moveaxis(net,0,1),int(p),axis=1)
    return SplineSurface(along,across)


def strips(first_end=0,second_end=0):
    a=np.array([[[0,0,0],[-1,0,0]],[[0,1,0],[-1,1,0]]],float)
    b=a.copy();b[:,:,0]*=-1
    if first_end==-1:a=a[:,::-1]
    if second_end==-1:b=b[:,::-1]
    return bezier(a),bezier(b)


def check(a,b,**options):
    return seam_projection_injectivity(a,0,b,0,**{'first_width':1.,'second_width':1.,
        'reference_min_mm':1e-12,'monotonic_margin':0.,**options})


@pytest.mark.parametrize('ends',[(0,0),(0,-1),(-1,0),(-1,-1)])
@pytest.mark.parametrize('refinements',[0,2])
def test_end_orientation_and_refinement_use_one_projection(ends,refinements):
    a,b=strips(*ends);before=deepcopy((a.across.c,b.across.c))
    r=seam_projection_injectivity(a,ends[0],b,ends[1],first_width=.3,second_width=.3,
        reference_min_mm=1e-12,monotonic_margin=0,refinements=refinements,span_range=(.2,.9))
    assert r['numeric_injective'] and r['min_symmetric_lower']==pytest.approx(1.)
    assert len(r['cells'])==2*4**refinements and r['required_cells']==len(r['cells'])
    assert {c['side'] for c in r['cells']}=={0,1}
    assert not r['coordinates_modified'] and not r['roundoff_certified']
    assert not r['whole_geometry_verified'] and not r['continuous_surface_certified']
    for source,old in zip((a,b),before):np.testing.assert_array_equal(source.across.c,old)


@pytest.mark.parametrize('scale',[.01,1.,100.])
def test_rigid_transform_scale_and_unequal_widths(scale):
    a,b=strips();q,_=np.linalg.qr(np.array([[1.,2,3],[-2,3,1],[3,1,-2]]))
    for s in (a,b):s.across.c=s.across.c@q*scale+[10,-20,30]
    r=check(a,b,first_width=.2,second_width=.6)
    assert r['numeric_injective'] and r['min_symmetric_lower']==pytest.approx(.5,abs=1e-10)


def test_continuous_kink_needs_no_g1_but_common_projection_must_hold():
    a,b=strips();b.across.c[:,:,2]=b.across.c[:,:,0]*.5
    r=check(a,b)
    assert r['numeric_injective'] and r['min_symmetric_lower']>0


def test_two_individually_injective_overlapping_sides_are_not_a_joined_chart():
    a,_=strips()
    assert surface_projection_injectivity(a,reference_min_mm=1e-12,monotonic_margin=0)['numeric_injective']
    r=check(a,a)
    assert not r['numeric_injective'] and r['reason']=='reference_rank'


def test_fold_away_from_reference_is_not_hidden_by_refinement():
    a,b=strips()
    # x(v)=v-2*v^2: positive at seam, folds and overlaps the negative side.
    b=bezier([[[0,0,0],[.5,0,0],[-1,0,0]],[[0,1,0],[.5,1,0],[-1,1,0]]])
    r=check(a,b,refinements=2)
    assert r['reason']=='symmetric_bound_not_positive' and not r['numeric_injective']
    assert r['min_symmetric_lower']<0
    assert check(a,b,second_width=.1)['numeric_injective']


def test_tiny_gap_is_unresolved_without_welding():
    a,b=strips();b.across.c[:,:,2]+=1e-15;before=b.across.c.copy()
    r=check(a,b)
    assert r['reason']=='boundary_representation_mismatch' and r['projection'] is None
    assert not r['numeric_injective'] and not r['cells']
    np.testing.assert_array_equal(b.across.c,before)


def test_same_geometric_curve_with_different_degree_is_conservatively_unresolved():
    a,b=strips();net=np.array([[[0,0,0],[1,0,0]],[[0,.5,0],[1,.5,0]],[[0,1,0],[1,1,0]]])
    b=bezier(net)
    assert check(a,b)['reason']=='boundary_representation_mismatch'


def test_rank_margin_and_resource_limits_never_return_partial_success():
    a,b=strips()
    assert check(a,b,reference_min_mm=1.)['reason']=='reference_rank'
    assert not check(a,b,monotonic_margin=1.)['numeric_injective']
    r=check(a,b,max_cells=1)
    assert r['status']=='RESOURCE_LIMIT' and not r['cells'] and r['projection'] is None
    assert r['required_cells']==2 and not r['numeric_injective']


@pytest.mark.parametrize('options',[{'first_width':0},{'second_width':1.1},{'first_width':True},
    {'first_width':float('nan')},{'reference_min_mm':-1},{'monotonic_margin':True},
    {'max_cells':0},{'refinements':True},{'span_range':(1,0)},{'span_range':(False,True)}])
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValueError):check(*strips(),**options)


@pytest.mark.parametrize('end',[True,1,-2])
def test_invalid_endpoint_is_not_reinterpreted(end):
    a,b=strips()
    with pytest.raises(ValueError):
        seam_projection_injectivity(a,end,b,0,first_width=1,second_width=1,
                                   reference_min_mm=0,monotonic_margin=0)


def test_discontinuous_source_is_rejected_even_when_boundary_matches():
    a,b=strips()
    b.along=BSpline([0,0,.5,.5,1,1],np.zeros((2,4,3)),1,axis=1)
    b.across.c=np.repeat(b.across.c,2,axis=1)
    with pytest.raises(ValueError,match='Discontinuous'):check(a,b)


def test_dense_independent_derivatives_are_above_both_side_bounds():
    a,b=strips()
    b=bezier([[[0,0,0],[.5,0,0],[1.2,0,0]],[[0,1,0],[.5,1,0],[1.2,1,0]]])
    r=check(a,b,refinements=2);projection=np.array(r['projection'])
    assert r['numeric_injective']
    for cell in r['cells']:
        for t in np.linspace(*cell['xi_range'],11):
            dx=1 if cell['side']==0 else 1+.4*t
            derivative=np.array([[0,dx],[1,0],[0,0]])
            matrix=projection@derivative
            assert np.linalg.eigvalsh((matrix+matrix.T)/2)[0]>=cell['symmetric_lower']-1e-12


def test_unrepresentable_width_at_end_is_rejected_without_empty_side():
    a,b=strips(-1,0)
    with pytest.raises(ValueError,match='representable'):
        seam_projection_injectivity(a,-1,b,0,first_width=1e-20,second_width=1,
                                   reference_min_mm=0,monotonic_margin=0)


def test_c0_internal_knot_uses_all_piecewise_derivatives():
    a,b=strips()
    for s in (a,b):
        net=s.across.c
        c=np.stack((net[0],(net[0]+net[1])/2,net[1]),axis=0)
        c[1,:,1]=.25
        s.across=BSpline([0,0,.5,1,1],np.moveaxis(c,0,1),1,axis=1)
    r=check(a,b)
    assert r['numeric_injective'] and r['required_cells']==4
    assert r['min_symmetric_lower']==pytest.approx(1/3)
