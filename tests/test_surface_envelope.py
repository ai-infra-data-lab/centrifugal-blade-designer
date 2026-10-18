"""Independent equations and hidden-interior negatives, not revised fixtures."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import make_interp_spline
from blade_designer.geometry.surface_evaluation import fit_surface_spline, compare_surfaces
from blade_designer.geometry.surface_envelope import surface_distance_envelope


def patch(function, density=9, spans=(0., .3, 1.)):
    t = np.linspace(0, 1, density)
    return fit_surface_spline([function(s, t) for s in spans], density, spans=spans)


def plane(s, t):
    return np.column_stack((t, np.full(len(t), s), 0*t))


@pytest.mark.parametrize('refinements', [0, 1, 2])
def test_same_surface_is_zero_and_inputs_unchanged(refinements):
    a = patch(plane)
    before = deepcopy((a.along.t, a.along.c, a.across.t, a.across.c))
    result = surface_distance_envelope(a, a, refinements=refinements)
    assert result['control_upper_mm'] == result['sample_lower_mm'] == 0
    assert result['roundoff_certified'] is False
    for old, new in zip(before, (a.along.t, a.along.c, a.across.t, a.across.c)):
        np.testing.assert_array_equal(old, new)


@pytest.mark.parametrize('refinements', [0, 1, 2])
def test_translated_plane_has_known_constant_distance_with_different_knots(refinements):
    a = patch(plane, 9)
    b = patch(lambda s,t: plane(s,t)+[1., 2., 3.], 17)
    result = surface_distance_envelope(a, b, refinements=refinements)
    assert result['control_upper_mm'] == pytest.approx(np.sqrt(14), abs=2e-14)
    assert result['sample_lower_mm'] == pytest.approx(np.sqrt(14), abs=2e-14)


def test_interior_bump_is_missed_at_corners_but_enclosed_globally():
    a = patch(plane, 3)
    b = patch(lambda s,t: plane(s,t)+np.column_stack((0*t,0*t,16*s*(1-s)*t*(1-t))), 3)
    assert compare_surfaces(a,b,[0,1],[0,1])['max_mm'] == 0
    coarse = surface_distance_envelope(a,b)
    refined = surface_distance_envelope(a,b,refinements=1)
    assert coarse['control_upper_mm'] == pytest.approx(4., abs=1e-14)
    assert coarse['sample_lower_mm'] == pytest.approx(1., abs=1e-14)
    assert refined['control_upper_mm'] == pytest.approx(1., abs=1e-14)
    assert refined['control_upper_mm'] < coarse['control_upper_mm']


@pytest.mark.parametrize('density', [9,17,33])
def test_common_basis_bounds_dense_difference_with_nonuniform_span_knots(density):
    a = patch(lambda s,t: np.column_stack((t,t**3+s**3,np.full(len(t),s))),9,(0.,.2,.7,1.))
    b = patch(lambda s,t: np.column_stack((t,t**3+s**3+.2*s*(1-s)*t,np.full(len(t),s))),density,(0.,.3,.8,1.))
    result = surface_distance_envelope(a,b,refinements=1)
    dense = compare_surfaces(a,b,np.linspace(0,1,61),np.linspace(0,1,101))['max_mm']
    assert result['sample_lower_mm'] <= result['control_upper_mm']+2e-14
    assert dense <= result['control_upper_mm']+2e-14
    assert result['control_upper_mm'] >= .05-2e-14  # Independent midpoint equation.


@pytest.mark.parametrize('bad', ['type','degrees','domain','coefficients','complex','axis','unclamped'])
def test_unsupported_inputs_are_rejected_without_repair(bad):
    a = patch(plane)
    b = deepcopy(a)
    if bad=='type': b=None
    elif bad=='degrees': b=patch(plane,2)
    elif bad=='domain': b.along.t[-4:]=2
    elif bad=='coefficients': b.across.c[0,0,0]=np.nan
    elif bad=='complex': b.across.c=b.across.c.astype(complex)+1j
    elif bad=='axis': b.across.axis=0
    elif bad=='unclamped': b.along.t[0]=-.1
    with pytest.raises(ValueError): surface_distance_envelope(a,b)


@pytest.mark.parametrize('refinements', [-1,5,True,1.5])
def test_invalid_refinement_is_not_silently_changed(refinements):
    a=patch(plane)
    with pytest.raises(ValueError,match='refinements'):
        surface_distance_envelope(a,a,refinements=refinements)


@pytest.mark.parametrize('cap', [0,True,1.5,5])
def test_invalid_or_exceeded_resource_limit_is_rejected(cap):
    a=patch(plane)
    with pytest.raises(ValueError): surface_distance_envelope(a,a,max_control_points=cap)


def test_interior_multiplicity_and_knot_insertion_preserve_the_model():
    a=patch(plane)
    b=deepcopy(a)
    b.along=b.along.insert_knot(.5,2)
    b.across=make_interp_spline([0.,.3,1.],b.along.c,k=2,axis=1)
    result=surface_distance_envelope(a,b)
    assert result['control_upper_mm'] < 1e-14


def test_periodic_boundary_wrapping_is_not_mistaken_for_same_surface():
    a=patch(plane)
    b=deepcopy(a)
    b.across.extrapolate='periodic'
    assert compare_surfaces(a,b,[1],[.5])['max_mm'] > .9
    with pytest.raises(ValueError,match='clamped'): surface_distance_envelope(a,b)


def test_precision_collapsed_refinement_is_rejected_not_merged():
    a=patch(plane)
    b=deepcopy(a)
    b.along.t[4]=np.nextafter(0.,1.)
    with pytest.raises(ValueError,match='precision'):
        surface_distance_envelope(a,b,refinements=1)
