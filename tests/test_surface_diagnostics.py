"""Analytic references; these do not approve existing design surfaces."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.surface_evaluation import fit_surface_spline
from blade_designer.geometry.surface_diagnostics import spline_differentials, compare_spline_differentials


def polynomial_surface(function, density=17):
    s = np.array([0., .2, .7, 1.])
    t = np.linspace(0, 1, density)
    return fit_surface_spline([function(v, t) for v in s], density, spans=s)


@pytest.mark.parametrize('density', [9, 17, 33])
def test_cubic_derivatives_and_oriented_jacobian_against_analytic_equations(density):
    model = polynomial_surface(lambda s, t: np.column_stack((t, t**3+s**3, np.full(len(t), s))), density)
    before = deepcopy((model.along.c, model.across.c))
    s, t = np.linspace(0, 1, 13), np.linspace(0, 1, 19)
    x, y = np.meshgrid(t, s)
    result = spline_differentials(model, s, t, singular_mm2=1e-10)
    ds = np.stack((0*y, 3*y*y, np.ones_like(y)), axis=-1)
    dt = np.stack((np.ones_like(x), 3*x*x, 0*x), axis=-1)
    cross = np.cross(ds, dt)
    jacobian = np.linalg.norm(cross, axis=-1)
    np.testing.assert_allclose(result.d_span, ds, atol=2e-13)
    np.testing.assert_allclose(result.d_xi, dt, atol=2e-13)
    np.testing.assert_allclose(result.jacobian_mm2, jacobian, atol=2e-13)
    np.testing.assert_allclose(result.normals, cross/jacobian[..., None], atol=2e-13)
    np.testing.assert_array_equal(result.xyz, model.evaluate_grid(s, t))
    assert not result.singular.any()
    for a, b in zip(before, (model.along.c, model.across.c)): np.testing.assert_array_equal(a, b)


def test_fold_singularity_is_explicit_and_normals_reverse_across_it():
    model = polynomial_surface(lambda s, t: np.column_stack((t, np.full(len(t), (s-.5)**2), 0*t)))
    result = spline_differentials(model, [.25, .5, .75], [0, .5, 1], singular_mm2=1e-12)
    np.testing.assert_array_equal(result.singular, [[False]*3, [True]*3, [False]*3])
    assert np.isnan(result.normals[1]).all()
    np.testing.assert_allclose(result.normals[0], [[0, 0, 1]]*3, atol=1e-14)
    np.testing.assert_allclose(result.normals[2], [[0, 0, -1]]*3, atol=1e-14)


@pytest.mark.parametrize('scale', [.01, 1., 100.])
def test_jacobian_has_square_length_units_and_threshold_is_explicit(scale):
    model = polynomial_surface(lambda s, t: scale*np.column_stack((t, np.full(len(t), s), 0*t)))
    result = spline_differentials(model, [.4], [.6], singular_mm2=.5*scale**2)
    assert result.jacobian_mm2.item() == pytest.approx(scale**2)
    assert not result.singular.item()
    assert spline_differentials(model, [.4], [.6], singular_mm2=2*scale**2).singular.item()


@pytest.mark.parametrize('angle', [0., 30., 90., 180.])
def test_corresponding_normal_comparison_keeps_orientation_and_known_distance(angle):
    # Exact linear patches avoid cubic fitting roundoff in constant coordinates.
    t = np.array([0., 1.])
    a = fit_surface_spline([np.column_stack((t, np.full(2, s), 0*t)) for s in (0., 1.)], 2)
    radians = np.radians(angle)
    b = fit_surface_spline([np.column_stack((t, np.full(2, s*np.cos(radians)), np.full(2, 2+s*np.sin(radians)))) for s in (0., 1.)], 2)
    result = compare_spline_differentials(a, b, [0, 1], [0, 1], singular_mm2=1e-12)
    assert result['max_normal_degrees'] == pytest.approx(angle, abs=1e-12)
    assert result['valid_normal_pairs'] == 4
    expected = np.array([2., np.hypot(np.cos(radians)-1, 2+np.sin(radians))])
    assert result['max_mm'] == pytest.approx(expected.max())
    assert result['rms_mm'] == pytest.approx(np.sqrt(np.mean(expected**2)))


def test_all_invalid_normals_return_none_not_zero_angle():
    a = polynomial_surface(lambda s, t: np.column_stack((t, 0*t, 0*t)))
    result = compare_spline_differentials(a, a, [0, .5, 1], [0, 1], singular_mm2=1e-12)
    assert result['max_normal_degrees'] is None
    assert result['valid_normal_pairs'] == 0
    assert result['first_singular_samples'] == result['second_singular_samples'] == 6


@pytest.mark.parametrize('bad', [-1, np.nan, np.inf, True, [1], 'x', None, 1j])
def test_invalid_threshold_is_rejected(bad):
    a = polynomial_surface(lambda s, t: np.column_stack((t, np.full(len(t), s), 0*t)))
    with pytest.raises(ValueError, match='singular_mm2'):
        spline_differentials(a, [0, 1], [0, 1], singular_mm2=bad)


@pytest.mark.parametrize('s,t', [([], [0]), ([0], [np.nan]), ([-.1], [0]), ([0], [1.1])])
def test_invalid_query_is_not_clamped(s, t):
    a = polynomial_surface(lambda s, t: np.column_stack((t, np.full(len(t), s), 0*t)))
    with pytest.raises(ValueError): spline_differentials(a, s, t, singular_mm2=0)


def test_unsupported_surface_is_rejected():
    with pytest.raises(ValueError, match='SplineSurface'):
        spline_differentials(None, [0], [0], singular_mm2=0)


def test_nonfinite_coefficients_are_rejected_without_normal_substitution():
    a = polynomial_surface(lambda s, t: np.column_stack((t, np.full(len(t), s), 0*t)))
    a.across.c[:] = np.nan
    with pytest.raises(ValueError, match='finite'):
        spline_differentials(a, [0, 1], [0, 1], singular_mm2=0)


def test_partial_singular_comparison_counts_all_missing_normal_pairs():
    a = polynomial_surface(lambda s, t: np.column_stack((t, np.full(len(t), (s-.5)**2), 0*t)))
    result = compare_spline_differentials(a, a, [.25, .5, .75], [0, 1], singular_mm2=1e-12)
    assert result['valid_normal_pairs'] == 4
    assert result['first_singular_samples'] == result['second_singular_samples'] == 2
    assert result['max_normal_degrees'] == 0


def test_unsampled_singularity_cannot_be_ruled_out_by_regular_samples():
    model = polynomial_surface(lambda s, t: np.column_stack((t, np.full(len(t), (s-.5)**2), 0*t)))
    result = spline_differentials(model, [.25, .75], [0, 1], singular_mm2=1e-12)
    assert not result.singular.any()  # Fold at .5 is deliberately not sampled.


def test_main_splitter_gap_rake_reference_patches_are_read_only():
    from blade_designer.models.parameters import BladeParameters, SplitterParameters, TipClearanceParameters
    from blade_designer.geometry.geometry_3d import generate_impeller
    from blade_designer.geometry.cad_surface_reference import reference_surfaces
    p = BladeParameters()
    p.impeller_te_rake_deg = 12.
    p.tip_clearance = TipClearanceParameters(.4, .8)
    p.splitter = SplitterParameters(sections=deepcopy(p.sections))
    before = deepcopy(p)
    geometry = generate_impeller(p)
    for sections in (geometry.sections, geometry.splitter_sections):
        for surface in reference_surfaces(sections, p.sections, 65).values():
            result = compare_spline_differentials(surface, surface, np.linspace(0, 1, 13), np.linspace(0, 1, 23), singular_mm2=1e-12)
            assert result['max_mm'] == 0
            assert result['max_normal_degrees'] == 0
            assert result['valid_normal_pairs'] + result['first_singular_samples'] == 13*23
    assert p == before
