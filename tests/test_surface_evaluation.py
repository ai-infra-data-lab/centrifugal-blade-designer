"""Independent analytic surfaces and explicit interpolation differences."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.surface_evaluation import (SectionSurface, fit_surface_spline,
    interpolate_span_columns, compare_surfaces)


def planar_rows():
    spans = np.array([0., .3, 1.])
    coordinates = [np.array([0., .2, 1.]), np.array([0., .4, .7, 1.]), np.array([0., 1.])]
    rows = [np.column_stack((p, 2*p+3*s, np.full(len(p), s))) for s, p in zip(spans, coordinates)]
    return rows, coordinates, spans


def test_piecewise_surface_plane_and_unequal_streamwise_sampling():
    rows, parameters, spans = planar_rows()
    before = deepcopy((rows, parameters, spans))
    surface = SectionSurface(rows, parameters, spans)
    s, t = np.linspace(0, 1, 13), np.linspace(0, 1, 19)
    x, y = np.meshgrid(t, s)
    np.testing.assert_allclose(surface.evaluate_grid(s, t), np.stack((x, 2*x+3*y, y), axis=-1), atol=1e-15)
    for a, b in zip(rows+parameters+[spans], before[0]+before[1]+[before[2]]):np.testing.assert_array_equal(a, b)
    rows[0][:] = 999
    assert np.max(surface.evaluate_grid([0], [0, 1])) < 10  # Owns its snapshot.


def test_cartesian_chord_and_cylindrical_arc_have_known_nonzero_difference():
    theta = [0., np.pi/2]
    cyl = [np.array([[10., a, 0.], [10., a, 2.]]) for a in theta]
    xyz = [np.column_stack((r[:, 0]*np.cos(r[:, 1]), r[:, 0]*np.sin(r[:, 1]), r[:, 2])) for r in cyl]
    params = [np.array([0., 1.])]*2
    cart = SectionSurface(xyz, params, np.array([0., 1.]))
    radial = SectionSurface(cyl, params, np.array([0., 1.]), cylindrical=True)
    a, b = cart.evaluate_grid([.5], [.5])[0, 0], radial.evaluate_grid([.5], [.5])[0, 0]
    np.testing.assert_allclose(a, [5, 5, 1], atol=1e-14)
    np.testing.assert_allclose(b, [np.sqrt(50), np.sqrt(50), 1], atol=1e-14)
    gap = compare_surfaces(cart, radial, [.5], [.5])
    assert gap['max_mm'] == pytest.approx(10*(1-np.cos(np.pi/4)))
    assert gap['rms_mm'] == gap['max_mm']


@pytest.mark.parametrize('density', [9, 17, 33])
def test_cad_tensor_spline_reproduces_independent_cubic_surface(density):
    spans, t = np.array([0., .2, .7, 1.]), np.linspace(0, 1, density)
    rows = [np.column_stack((t, t**3+s**3, np.full(len(t), s))) for s in spans]
    model = fit_surface_spline(rows, density, spans=spans)
    query_s, query_t = np.linspace(0, 1, 23), np.linspace(0, 1, 29)
    x, y = np.meshgrid(query_t, query_s)
    np.testing.assert_allclose(model.evaluate_grid(query_s, query_t), np.stack((x, x**3+y**3, y), axis=-1), atol=2e-15)


def test_corresponding_grid_error_is_not_only_measured_at_input_spans():
    spans, t = np.array([0., .2, .7, 1.]), np.linspace(0, 1, 17)
    rows = [np.column_stack((t, t+s**3, np.full(len(t), s))) for s in spans]
    piecewise = SectionSurface(rows, [t]*len(rows), spans)
    spline = fit_surface_spline(rows, len(t), spans=spans)
    assert compare_surfaces(piecewise, spline, spans, t)['max_mm'] < 1e-14
    assert compare_surfaces(piecewise, spline, [.45], t)['max_mm'] == pytest.approx((.2**3+.7**3)/2-.45**3)


def test_clamped_end_tangents_match_analytic_surface():
    spans, t = np.array([0., 1.]), np.linspace(0, 1, 17)
    rows = [np.column_stack((t, t**3+s, np.full(len(t), s))) for s in spans]
    tangents = np.array([[[1, 0, 0]]*2, [[1, 3, 0]]*2], dtype=float)
    model = fit_surface_spline(rows, len(t), spans=spans, tangents=tangents)
    np.testing.assert_allclose(model.along.derivative()(0), tangents[0], atol=1e-14)
    np.testing.assert_allclose(model.along.derivative()(1), tangents[1], atol=1e-14)


def test_column_blend_preserves_scalar_and_xyz_values_at_nonuniform_spans():
    spans = np.array([0., .2, 1.]);target = np.array([0., .1, .2, .6, 1.])
    values = np.array([np.arange(5)+3*s for s in spans])
    np.testing.assert_allclose(interpolate_span_columns(values, spans, target), np.arange(5)+3*target, atol=1e-15)
    vectors = np.stack((values, 2*values, 3*values), axis=-1)
    expected = np.arange(5)+3*target
    np.testing.assert_allclose(interpolate_span_columns(vectors, spans, target), np.column_stack((expected, 2*expected, 3*expected)), atol=1e-14)


@pytest.mark.parametrize('bad', ['rows', 'nan', 'spans', 'duplicate_span', 'coordinate_order', 'coordinate_count', 'coordinate_domain', 'radius'])
def test_invalid_patch_is_rejected_without_repair(bad):
    rows, parameters, spans = planar_rows()
    if bad == 'rows': rows = rows[:1]
    elif bad == 'nan': rows[0][0, 0] = np.nan
    elif bad == 'spans': spans[-1] = .9
    elif bad == 'duplicate_span': spans[1] = 0
    elif bad == 'coordinate_order': parameters[0][1] = 0
    elif bad == 'coordinate_count': parameters[0] = np.array([0., 1.])
    elif bad == 'coordinate_domain': parameters[0][1] = -.1
    elif bad == 'radius': rows[0][0, 0] = -1
    with pytest.raises(ValueError):SectionSurface(rows, parameters, spans, cylindrical=bad == 'radius')


@pytest.mark.parametrize('query', [[-.1], [1.1], [np.nan], [], [[.5]]])
def test_queries_do_not_silently_clamp_or_extrapolate(query):
    rows, parameters, spans = planar_rows()
    for surface in (SectionSurface(rows, parameters, spans), fit_surface_spline(rows, 33, parameters, spans)):
        with pytest.raises(ValueError):surface.evaluate_grid(query, [.5])
        with pytest.raises(ValueError):surface.evaluate_grid([.5], query)


@pytest.mark.parametrize('count', [True, 1, 3.5])
def test_invalid_spline_density(count):
    rows, parameters, spans = planar_rows()
    with pytest.raises(ValueError):fit_surface_spline(rows, count, parameters, spans)
