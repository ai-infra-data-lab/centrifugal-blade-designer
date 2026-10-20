"""Strong monotonicity is stronger than nonzero area and is domain scoped."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import BSpline
from blade_designer.geometry.surface_injectivity import surface_projection_injectivity,local_source_pair_injectivity
from blade_designer.geometry.surface_evaluation import SplineSurface
from blade_designer.geometry.surface_regularity import surface_jacobian_envelope
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
from test_surface_envelope import patch,plane
from test_conforming_role_grids import surfaces


def check(surface,**options):
    return surface_projection_injectivity(surface,**{'reference_min_mm':1e-12,'monotonic_margin':0.,**options})


@pytest.mark.parametrize('scale',[.01,1.,100.])
@pytest.mark.parametrize('refinements',[0,1])
def test_affine_plane_rigid_transform_scale_and_restriction(scale,refinements):
    a=patch(plane,2,(0.,1.));q,_=np.linalg.qr(np.array([[1.,2,3],[-2,3,1],[3,1,-2]]))
    a.across.c=a.across.c@q*scale+[10,-20,30];before=deepcopy(a.across.c)
    r=check(a,span_range=(.1,.8),xi_range=(.2,.9),refinements=refinements)
    assert r['numeric_injective'] and r['min_symmetric_lower']==pytest.approx(1.,abs=1e-11)
    assert len(r['cells'])==4**refinements
    assert not r['roundoff_certified'] and not r['whole_geometry_verified']
    np.testing.assert_array_equal(a.across.c,before)


def test_positive_jacobian_self_crossing_is_not_declared_injective():
    a=patch(lambda s,t:np.column_stack((0*t+(s-.25)*(s-.75),
                                      0*t+(s-.25)*(s-.75)*(s-.5),t)),4,(0.,.2,.7,1.))
    np.testing.assert_allclose(a.evaluate_grid([.25],[.4]),a.evaluate_grid([.75],[.4]),atol=1e-14)
    assert surface_jacobian_envelope(a,singular_mm2=1e-12,refinements=4)['unresolved_cells']==0
    r=check(a,refinements=2)
    assert r['status']=='UNRESOLVED' and not r['numeric_injective']


def test_hidden_fold_is_unresolved_but_a_monotone_subrectangle_is_injective():
    a=patch(lambda s,t:np.column_stack((t,0*t+(s-.37)**2,0*t)),4,(0.,.2,.7,1.))
    assert not check(a)['numeric_injective']
    assert check(a,span_range=(.4,1.))['numeric_injective']


def test_rank_deficient_reference_stays_unresolved_without_pseudoinverse_repair():
    a=patch(lambda s,t:np.column_stack((t,0*t,0*t)),2,(0.,1.))
    r=check(a)
    assert r['reason']=='reference_rank' and r['projection'] is None
    assert not r['numeric_injective'] and not r['cells']


def test_reference_rank_and_monotonic_thresholds_are_strict():
    a=patch(plane,2,(0.,1.))
    assert check(a,reference_min_mm=1.)['reason']=='reference_rank'
    assert not check(a,monotonic_margin=1.)['numeric_injective']
    assert check(a,monotonic_margin=.99)['numeric_injective']


def test_continuous_piecewise_linear_chart_is_checked_with_one_common_projection():
    along=BSpline([0,0,1,1],np.zeros((2,2,3)),1,axis=1)
    coefficients=np.array([[[0.,0,0],[1,0,0]],[[0,.5,0],[1,.5,0]],[[0,1.5,0],[1,1.5,0]]])
    across=BSpline([0,0,.5,1,1],np.moveaxis(coefficients,0,1),1,axis=1)
    r=check(SplineSurface(along,across))
    assert r['numeric_injective'] and len(r['cells'])==2
    assert r['min_symmetric_lower']==pytest.approx(.5)


def test_discontinuous_source_is_rejected_instead_of_joined():
    along=BSpline([0,0,1,1],np.zeros((2,2,3)),1,axis=1)
    across=BSpline([0,0,.5,.5,1,1],np.zeros((2,4,3)),1,axis=1)
    with pytest.raises(ValueError,match='Discontinuous'):check(SplineSurface(along,across))


def test_projected_derivative_lower_encloses_independent_dense_eigenvalues():
    a=patch(lambda s,t:plane(s,t)+np.column_stack((0*t,0*t,.2*s*s+.1*t**3)),4,(0.,.2,.7,1.))
    r=check(a,span_range=(.2,.8),xi_range=(.1,.9),refinements=1)
    assert r['numeric_injective'];projection=np.array(r['projection'])
    for cell in r['cells']:
        for s in np.linspace(*cell['span_range'],7):
            for t in np.linspace(*cell['xi_range'],7):
                derivative=np.array([[0,1],[1,0],[.4*s,.3*t*t]])*np.array([.6,.8])
                matrix=projection@derivative
                eigen=np.linalg.eigvalsh((matrix+matrix.T)/2)[0]
                assert eigen>=cell['symmetric_lower']-1e-12


def test_resource_limit_does_not_return_partial_positive_cells():
    r=check(patch(plane),refinements=4,max_cells=1)
    assert r['status']=='RESOURCE_LIMIT' and not r['cells'] and not r['numeric_injective']


def test_neighboring_source_triangles_use_their_complete_enclosing_rectangle():
    source=surfaces();envelope=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)
    r=local_source_pair_injectivity(source,envelope,0,1,reference_min_mm=1e-12,monotonic_margin=0)
    assert r['expected_parameter_contact_only'] and r['source_identity_checked']
    assert r['projection_report']['span_range']==[0,1]
    assert not r['whole_geometry_verified']


def test_cross_role_neighbors_require_a_seam_chart_not_two_separate_positive_checks():
    source=surfaces();e=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)
    m=e['mesh'];pair=next((i,j) for i in range(len(m['faces'])) for j in range(i+1,len(m['faces']))
                        if m['face_roles'][i]!=m['face_roles'][j] and set(m['faces'][i])&set(m['faces'][j]))
    r=local_source_pair_injectivity(source,e,*pair,reference_min_mm=1e-12,monotonic_margin=0)
    assert r['reason']=='cross_role_requires_seam_chart' and not r['expected_parameter_contact_only']


def test_valid_shear_can_be_unresolved_and_separate_local_charts_cannot_be_glued():
    # Exact inverse: s=X, t=Y-10*X**2. This surface is injective everywhere.
    a=patch(lambda s,t:np.column_stack((0*t+s,t+10*s*s,0*t)),3,(0.,.5,1.))
    assert not check(a)['numeric_injective']
    for lo in (0.,.25,.5,.75):assert check(a,span_range=(lo,lo+.25))['numeric_injective']
    # Positivity using four different projections must not make the union pass.
    assert not check(a,refinements=2)['numeric_injective']


def test_two_neighboring_cells_use_union_bounds_and_resource_status():
    source=surfaces(mixed=True);e=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)
    kwargs={'reference_min_mm':1e-12,'monotonic_margin':0}
    r=local_source_pair_injectivity(source,e,0,3,**kwargs)
    assert r['expected_parameter_contact_only'] and r['projection_report']['required_cells']>=2
    limited=local_source_pair_injectivity(source,e,0,3,**kwargs,refinements=4,max_cells=1)
    assert limited['status']=='RESOURCE_LIMIT' and not limited['expected_parameter_contact_only']


def test_stale_source_and_invalid_neighbor_queries_rejected():
    source=surfaces();e=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)
    for pair in ((0,0),(0,4)):
        with pytest.raises(ValueError):local_source_pair_injectivity(source,e,*pair,reference_min_mm=1e-12,monotonic_margin=0)
    source['le'].across.c[1,1,0]+=.01
    with pytest.raises(ValueError,match='Source surface changed'):
        local_source_pair_injectivity(source,e,0,1,reference_min_mm=1e-12,monotonic_margin=0)


@pytest.mark.parametrize('options',[{'reference_min_mm':True},{'reference_min_mm':-1},
    {'monotonic_margin':np.nan},{'monotonic_margin':-1},{'refinements':True},{'refinements':5},
    {'max_cells':False},{'max_cells':0},{'span_range':(0,0)},{'xi_range':(1,0)},
    {'span_range':(0,np.inf)},{'xi_range':(False,True)},{'span_range':(-.1,1)}])
def test_invalid_arguments_rejected(options):
    with pytest.raises(ValueError):check(patch(plane),**options)
