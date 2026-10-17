"""Independent provenance analytics, real trim paths, and serialization boundary."""
from copy import deepcopy
from types import SimpleNamespace
import json
import numpy as np
import pytest
from blade_designer.models.geometry_3d import Curve3D, CurveSourceMap
from blade_designer.models.parameters import ImpellerTrimParameters, TipClearanceParameters, SplitterParameters, RotationDirection
from blade_designer.geometry.curve_source import evaluate_source_curve, source_map
from blade_designer.geometry.impeller_trim import _crop_curve, _span_curve
from blade_designer.geometry.blade_section import resample_curve
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.fileio.project_io import load_project, save_project
from test_cylindrical_cutoff import radial_parameters


def bilinear_example():
    # r(s,t)=10+10s+20t+20st. A blend of evaluated points is not
    # evaluation at the blended (s,t): the mixed term must be retained.
    source = SimpleNamespace(sections=[SimpleNamespace(span=s, master_ps=Curve3D(
        np.array([10+10*s, 30+30*s]), np.zeros(2), np.full(2, 4*s))) for s in (0., 1.)])
    curve = Curve3D(np.array([16.8, 46.8]), np.zeros(2), np.array([.8, 3.2]),
        source_map=CurveSourceMap('sections', 'master_ps', 'trim_common_index',
            np.array([[[.2, .2]], [[.8, .8]]]), np.ones((2, 1))))
    return source, curve


def test_od_intersection_retains_endpoint_blend_not_averaged_source_coordinates():
    source, curve = bilinear_example()
    cut = _crop_curve(curve, 31.8)
    np.testing.assert_allclose(evaluate_source_curve(cut, source), cut.xyz, atol=1e-14, rtol=0)
    np.testing.assert_allclose(cut.source_map.weights[-1], [.5, .5], atol=1e-15)
    average = np.sum(cut.source_map.coordinates[-1]*cut.source_map.weights[-1, :, None], axis=0)
    s, t = average
    naive_radius = 10+10*s+20*t+20*s*t
    assert cut.r[-1]-naive_radius == pytest.approx(1.8)
    np.testing.assert_array_equal(curve.source_map.weights, np.ones((2, 1)))


@pytest.mark.parametrize('points', [3, 11, 37])
def test_display_resampling_preserves_weighted_cylindrical_source(points):
    source, curve = bilinear_example()
    cut = _crop_curve(curve, 31.8)
    display = resample_curve(cut, points)
    assert display.source_map.weights.shape == (points, 4)
    np.testing.assert_allclose(evaluate_source_curve(display, source), display.xyz, atol=2e-14, rtol=0)


def test_source_row_law_preserves_hub_knots_with_unequal_row_point_counts():
    a = Curve3D(np.array([10., 12., 19.]), np.zeros(3), np.zeros(3))
    b = Curve3D(np.array([10., 13., 14., 19.]), np.zeros(4), np.ones(4))
    rows = [SimpleNamespace(span=0., master_ps=a), SimpleNamespace(span=1., master_ps=b)]
    curve = _span_curve(rows, 'master_ps', None, 0.)
    assert curve.source_map.law == 'source_row_index'
    np.testing.assert_array_equal(evaluate_source_curve(curve, SimpleNamespace(sections=rows)), a.xyz)


def test_resampling_with_one_retained_arclength_knot_uses_constant_provenance():
    curve = Curve3D(np.array([10., np.nextafter(10., 11.)]), np.zeros(2), np.zeros(2),
        source_map=source_map(0., 2, 'master_ps'))
    source = SimpleNamespace(sections=[SimpleNamespace(span=s, master_ps=deepcopy(curve)) for s in (0., 1.)])
    display = resample_curve(curve, 5)
    np.testing.assert_array_equal(evaluate_source_curve(display, source), display.xyz)


def test_filtered_tiny_final_segment_clamps_source_weights_like_geometry():
    curve = Curve3D(np.array([10., 11., np.nextafter(11., 12.)]), np.zeros(3), np.zeros(3),
        source_map=source_map(0., 3, 'master_ps'))
    source = SimpleNamespace(sections=[SimpleNamespace(span=s, master_ps=deepcopy(curve)) for s in (0., 1.)])
    display = resample_curve(curve, 5)
    assert display.r[-1] == 11. and np.all(display.source_map.weights >= 0)
    reconstructed = evaluate_source_curve(display, source)
    np.testing.assert_array_equal(reconstructed[-1], display.xyz[-1])
    # The weighted sum and np.interp differ by one floating-point ULP inside
    # the segment; the clamped endpoint and nonnegative weights remain exact.
    np.testing.assert_array_max_ulp(reconstructed, display.xyz, maxulp=1)


@pytest.mark.parametrize('bad', ['missing', 'role', 'set', 'law', 'shape', 'negative', 'sum', 'nan', 'coordinate'])
def test_invalid_source_map_is_rejected_without_repair(bad):
    source, curve = bilinear_example();before = curve.xyz.copy()
    if bad == 'missing':curve.source_map = None
    elif bad == 'role':curve.source_map.role = 'not_a_role'
    elif bad == 'set':curve.source_map.source_set = 'not_a_set'
    elif bad == 'law':curve.source_map.law = 'xyz'
    elif bad == 'shape':curve.source_map.weights = np.ones((3, 1))
    elif bad == 'negative':curve.source_map.weights[0, 0] = -1
    elif bad == 'sum':curve.source_map.weights[0, 0] = .5
    elif bad == 'nan':curve.source_map.coordinates[0, 0, 0] = np.nan
    elif bad == 'coordinate':curve.source_map.coordinates[0, 0, 1] = 1.1
    with pytest.raises(ValueError):evaluate_source_curve(curve, source)
    np.testing.assert_array_equal(curve.xyz, before)


@pytest.mark.parametrize('mode', ['shroud', 'od', 'combined'])
@pytest.mark.parametrize('splitter', [False, True])
@pytest.mark.parametrize('rotation', list(RotationDirection))
def test_generated_main_splitter_and_display_reconstruct_without_changing_parameters(mode, splitter, rotation):
    p = radial_parameters();p.tip_clearance = TipClearanceParameters(.4, .8);p.impeller_te_rake_deg = 12.
    p.rotation_direction = rotation
    if splitter:p.splitter = SplitterParameters(sections=deepcopy(p.sections))
    p.impeller_trim = ImpellerTrimParameters(10 if mode != 'od' else 0,
        'percent' if mode != 'shroud' else 'off', 0, 5)
    before = deepcopy(p);geometry = generate_impeller(p);assert p == before
    for name in ('sections', 'splitter_sections'):
        for section in getattr(geometry, name) or []:
            for role in ('camber', 'master_ps', 'master_ss', 'master_le', 'master_te'):
                curve = getattr(section, role)
                if role == 'master_te' and mode != 'shroud':
                    assert curve.source_map is None
                    with pytest.raises(ValueError, match='machined TE'):evaluate_source_curve(curve, geometry.source_geometry)
                    continue
                assert curve.source_map.source_set == name and curve.source_map.role == role
                np.testing.assert_allclose(evaluate_source_curve(curve, geometry.source_geometry), curve.xyz, atol=8e-13, rtol=0)
            for role in ('ps', 'ss'):
                curve = getattr(section, role)
                np.testing.assert_allclose(evaluate_source_curve(curve, geometry.source_geometry), curve.xyz, atol=8e-13, rtol=0)
    for section in geometry.source_geometry.sections:
        assert section.master_ps.source_map is None  # Base is never annotated in place.


def test_no_trim_has_no_derived_source_map():
    geometry = generate_impeller(radial_parameters())
    assert geometry.source_geometry is None
    assert all(s.master_ps.source_map is None for s in geometry.sections)


def test_project_json_contains_only_design_values_and_recreates_source_maps(tmp_path):
    p = radial_parameters();p.impeller_trim = ImpellerTrimParameters(10, 'percent', 0, 5)
    path = tmp_path/'design.json';save_project(path, p)
    before = path.read_bytes();geometry = generate_impeller(p);save_project(path, p)
    assert path.read_bytes() == before
    payload = json.loads(before)
    assert 'source_map' not in json.dumps(payload)
    reloaded = generate_impeller(load_project(path))
    np.testing.assert_array_equal(reloaded.sections[-1].master_ps.xyz, geometry.sections[-1].master_ps.xyz)
    np.testing.assert_array_equal(reloaded.sections[-1].master_ps.source_map.coordinates,
                                  geometry.sections[-1].master_ps.source_map.coordinates)
