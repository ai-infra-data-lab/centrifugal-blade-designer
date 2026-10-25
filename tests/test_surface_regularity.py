"""Analytic Jacobians and deliberately missed interior singularities."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import BSpline
from blade_designer.geometry.surface_evaluation import fit_surface_spline, SplineSurface
from blade_designer.geometry.surface_diagnostics import spline_differentials
from blade_designer.geometry.surface_regularity import surface_jacobian_envelope


def patch(function, density=9, spans=(0.,.2,.7,1.)):
    t=np.linspace(0,1,density)
    return fit_surface_spline([function(s,t) for s in spans],density,spans=spans)


@pytest.mark.parametrize('scale',[.01,1.,100.])
@pytest.mark.parametrize('refinements',[0,1])
def test_plane_has_exact_square_length_jacobian_and_is_read_only(scale,refinements):
    a=patch(lambda s,t:scale*np.column_stack((t,np.full(len(t),s),0*t)))
    before=deepcopy((a.along.t,a.along.c,a.across.t,a.across.c))
    result=surface_jacobian_envelope(a,singular_mm2=1e-12,refinements=refinements)
    assert result['min_lower_mm2']==pytest.approx(scale**2,rel=1e-10)
    assert result['max_upper_mm2']==pytest.approx(scale**2,rel=1e-10)
    assert result['numeric_regular_cells']==result['cell_count']
    assert result['unresolved_cells']==0 and result['roundoff_certified'] is False
    for x,y in zip(before,(a.along.t,a.along.c,a.across.t,a.across.c)):np.testing.assert_array_equal(x,y)


def test_fold_between_samples_remains_unresolved_even_when_no_sample_is_singular():
    a=patch(lambda s,t:np.column_stack((t,np.full(len(t),(s-.37)**2),0*t)),4)
    observed=spline_differentials(a,[0,.5,1],[0,.5,1],singular_mm2=1e-12)
    assert not observed.singular.any()
    result=surface_jacobian_envelope(a,singular_mm2=1e-12)
    assert result['min_lower_mm2']==0
    assert result['unresolved_cells']>0
    assert result['sampled_at_or_below_threshold_cells']==0
    for cell in result['cells']:
        if cell['span_range'][0] < .37 < cell['span_range'][1]:assert not cell['numeric_regular']


def test_sampled_fold_and_collapsed_patch_are_not_reported_regular():
    for location in (.5,None):
        a=patch(lambda s,t:np.column_stack((t,np.full(len(t),0 if location is None else (s-location)**2),0*t)),4)
        result=surface_jacobian_envelope(a,singular_mm2=1e-12)
        assert result['sampled_at_or_below_threshold_cells']>0
        assert result['numeric_regular_cells']==0


def test_cubic_surface_cell_envelopes_contain_independent_dense_jacobian():
    a=patch(lambda s,t:np.column_stack((t,t**3+s**3,np.full(len(t),s))),17,(0.,.1,.35,.8,1.))
    result=surface_jacobian_envelope(a,singular_mm2=1e-12,refinements=1)
    for cell in result['cells']:
        s=np.linspace(*cell['span_range'],11)[:,None]
        t=np.linspace(*cell['xi_range'],13)[None,:]
        exact=np.sqrt(1+9*s**4+9*t**4)
        assert cell['lower_mm2'] <= exact.min()+2e-12
        assert cell['upper_mm2'] >= exact.max()-2e-12
    assert result['unresolved_cells']==0


def test_jacobian_bounds_are_translation_invariant_for_exact_dyadic_poles():
    surface=patch(lambda s,t:np.column_stack((t,np.full(len(t),s),t*s+s*s)),4)
    # Both the poles and the power-of-two translation are exactly representable.
    # Center before knot insertion so the arithmetic sees the same small net.
    surface.across.c[:]=np.round(surface.across.c*16)/16
    moved=deepcopy(surface);moved.across.c+=np.array([2.**20,-2.**21,2.**19])
    before=deepcopy((surface.across.c,moved.across.c))
    results=[surface_jacobian_envelope(s,singular_mm2=1e-12,refinements=2) for s in (surface,moved)]
    bounds=[np.array([[cell['lower_mm2'],cell['upper_mm2']] for cell in result['cells']]) for result in results]
    np.testing.assert_array_equal(bounds[0],bounds[1])
    np.testing.assert_array_equal(surface.across.c,before[0]);np.testing.assert_array_equal(moved.across.c,before[1])
    assert all(result['roundoff_certified'] is False for result in results)


def test_nonzero_jacobian_does_not_prove_global_nonintersection():
    # Two distinct interior parameters cross transversely. The two curve
    # derivatives never vanish together, including at s=.5.
    a=patch(lambda s,t:np.column_stack((np.full(len(t),(s-.25)*(s-.75)),
                                       np.full(len(t),(s-.25)*(s-.75)*(s-.5)),t)),4)
    np.testing.assert_allclose(a.evaluate_grid([.25],[.4]),a.evaluate_grid([.75],[.4]),atol=1e-14)
    result=surface_jacobian_envelope(a,singular_mm2=1e-12,refinements=4)
    assert result['unresolved_cells']==0
    assert 'self_intersection_free' not in result


def test_original_c0_seam_is_rejected_instead_of_smoothed():
    t=[0,0,.5,1,1]
    along=BSpline(t,np.zeros((2,3,3)),1,axis=1)
    across=BSpline([0,0,1,1],np.zeros((3,2,3)),1,axis=1)
    a=SplineSurface(along,across)
    with pytest.raises(ValueError,match='C1'):surface_jacobian_envelope(a,singular_mm2=0)


@pytest.mark.parametrize('threshold',[-1,np.nan,np.inf,True,[1]])
def test_invalid_threshold_rejected(threshold):
    a=patch(lambda s,t:np.column_stack((t,np.full(len(t),s),0*t)))
    with pytest.raises(ValueError,match='singular_mm2'):surface_jacobian_envelope(a,singular_mm2=threshold)


@pytest.mark.parametrize('refinements',[-1,5,True,1.5])
def test_invalid_refinement_rejected(refinements):
    a=patch(lambda s,t:np.column_stack((t,np.full(len(t),s),0*t)))
    with pytest.raises(ValueError,match='refinements'):
        surface_jacobian_envelope(a,singular_mm2=0,refinements=refinements)


@pytest.mark.parametrize('cap',[0,True,1.5,1])
def test_resource_budget_is_enforced(cap):
    a=patch(lambda s,t:np.column_stack((t,np.full(len(t),s),0*t)))
    with pytest.raises(ValueError,match='max_cells'):surface_jacobian_envelope(a,singular_mm2=0,max_cells=cap)
