"""Analytic correspondence checks and actual generated display/trim paths."""
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import numpy as np
import pytest
from blade_designer.models.geometry_3d import Curve3D
from blade_designer.geometry.blade_section import resample_curve
from blade_designer.geometry.surface_correspondence import (cad_curve_coordinates,
    display_master_coordinates, curve_provenance, trim_index_surface, compare_preview_to_spline)
from blade_designer.geometry.surface_evaluation import fit_surface_spline
from blade_designer.geometry.geometry_3d import generate_impeller, generate_diffuser_3d
from blade_designer.models.blade_rows import row_parameters
from blade_designer.fileio.project_io import load_project
from blade_designer.models.parameters import ImpellerTrimParameters, TipClearanceParameters, SplitterParameters
from test_cylindrical_cutoff import radial_parameters


@pytest.mark.parametrize('with_m', [False, True])
def test_display_coordinate_uses_arclength_not_uniform_index(with_m):
    master = Curve3D(np.array([10., 11., 14.]), np.zeros(3), np.zeros(3),
                     np.array([.35, .5, 1.]) if with_m else None)
    display = resample_curve(master, 5)
    actual = display_master_coordinates(master, display)
    source = np.array([0., .15/.65, 1.]) if with_m else np.array([0., .5, 1.])
    np.testing.assert_allclose(actual, np.interp(np.arange(5), [0, 1, 4], source), atol=1e-15)
    assert actual[1] != .25


def test_stale_display_is_rejected_without_mutation():
    master = Curve3D(np.array([10., 11., 14.]), np.zeros(3), np.zeros(3))
    display = resample_curve(master, 5);display.z[2] = 1
    before = display.xyz.copy()
    with pytest.raises(ValueError, match='current master'):display_master_coordinates(master, display)
    np.testing.assert_array_equal(display.xyz, before)


@pytest.mark.parametrize('source', [None, np.array([.2, .4, .7])])
def test_source_span_is_separate_from_nominal_and_cad_coordinates(source):
    curve = Curve3D(np.array([10., 11., 14.]), np.zeros(3), np.zeros(3),
                    np.array([.35, .5, .9]), source_span=source)
    result = curve_provenance(curve, .8)
    np.testing.assert_allclose(result.cad_xi, [0, .15/.55, 1], atol=1e-15)
    np.testing.assert_array_equal(result.index, [0, .5, 1])
    np.testing.assert_array_equal(result.source_span, np.full(3, .8) if source is None else source)
    assert result.source_span_kind == ('nominal_section' if source is None else 'original_geometry')
    result.source_span[:] = 0
    if source is not None:np.testing.assert_array_equal(source, [.2, .4, .7])


@pytest.mark.parametrize('bad', [[0, 0, 1], [0, np.nan, 1], [0, 1]])
def test_bad_master_coordinates_are_not_silently_repaired(bad):
    curve = Curve3D(np.ones(3), np.zeros(3), np.arange(3.), np.array(bad))
    with pytest.raises(ValueError):cad_curve_coordinates(curve)


def test_trim_common_index_is_cylindrical_and_not_master_m():
    a = Curve3D(np.array([10., 12., 14.]), np.zeros(3), np.zeros(3), np.array([0., .1, 1.]))
    b = Curve3D(np.array([20., 24.]), np.full(2, np.pi/2), np.full(2, 4.), np.array([0., 1.]))
    rows = [SimpleNamespace(span=0., master_ps=a), SimpleNamespace(span=1., master_ps=b)]
    surface = trim_index_surface(rows, 'master_ps')
    # At common index .5: source radii 12,22, span=.25 gives r=14.5.
    actual = surface.evaluate_grid([.25], [.5])[0, 0]
    np.testing.assert_allclose(actual, [14.5*np.cos(np.pi/8), 14.5*np.sin(np.pi/8), 1.], atol=1e-14)
    assert actual[0] != pytest.approx(.75*12)  # XYZ chord is a different path.


@pytest.mark.parametrize('fraction', [.3, 1.])
def test_actual_trim_vertices_reconstruct_from_common_index_and_source_span(fraction):
    from blade_designer.geometry.impeller_trim import _span_curve
    a = Curve3D(np.array([10., 12., 14.]), np.zeros(3), np.zeros(3), np.array([0., .1, 1.]))
    b = Curve3D(np.array([20., 24.]), np.full(2, np.pi/2), np.full(2, 4.), np.array([0., 1.]))
    rows = [SimpleNamespace(span=0., master_ps=a), SimpleNamespace(span=1., master_ps=b)]
    boundary = SimpleNamespace(signed=lambda zr: 3-zr[:, 0])
    cut = _span_curve(rows, 'master_ps', boundary, fraction)
    np.testing.assert_allclose(cut.source_span, .75*fraction, atol=2e-13, rtol=0)
    surface = trim_index_surface(rows, 'master_ps')
    expected = np.array([surface.evaluate_grid([s], [t])[0, 0]
                         for s, t in zip(cut.source_span, np.linspace(0, 1, len(cut.r)))])
    np.testing.assert_allclose(cut.xyz, expected, atol=1e-14, rtol=0)


def test_actual_wireframe_comparison_has_independent_twisted_chord_reference():
    sections = []
    for span, theta in [(0., 0.), (1., np.pi/2)]:
        curve = Curve3D(np.full(3, 10.), np.full(3, theta), np.arange(3.))
        data = {name: resample_curve(curve, 5) for name in ('le', 'ps', 'te', 'ss')}
        data.update({'master_'+name: curve for name in ('le', 'ps', 'te', 'ss')})
        sections.append(SimpleNamespace(span=span, **data))
    # Linear CAD in span equals the Cartesian displayed chord, not a cylinder.
    spline = fit_surface_spline([s.master_ps.xyz for s in sections], 9)
    report = compare_preview_to_spline(sections, 'ps', spline, [0., .5, 1.])
    assert report['max_mm'] < 1e-14
    assert report['display_lines'] == 5 and report['max_row_xi_spread'] == 0


def generated_case(case):
    if case in ('Impeller', 'Diffuser', 'RC'):
        project = load_project(Path(__file__).resolve().parents[1]/'blade_designer/defaults/default_project.json')
        row = next(row for row in project.blade_rows if row.name == case)
        p = row_parameters(project, row)
        return generate_impeller(p) if row.kind == 'impeller' else generate_diffuser_3d(p)
    p = radial_parameters()
    p.tip_clearance = TipClearanceParameters(.4, .8)
    p.impeller_te_rake_deg = 12.
    p.splitter = SplitterParameters(sections=deepcopy(p.sections))
    if case == 'trim':p.impeller_trim = ImpellerTrimParameters(10, 'percent', 0, 5)
    return generate_impeller(p)


@pytest.mark.parametrize('case', ['Impeller', 'Diffuser', 'RC', 'rake_gap_splitter', 'trim'])
def test_real_generated_display_maps_and_trim_provenance(case):
    geometry = generated_case(case)
    for sections in (geometry.sections, geometry.splitter_sections or []):
        for section in sections:
            for role in ('le', 'ps', 'te', 'ss'):
                master = getattr(section, 'master_'+role)
                # OD machining creates a new TE cap. It has no invertible m axis
                # when PS and SS have equal endpoint m; CAD trim remains blocked.
                if case == 'trim' and role == 'te':continue
                xi = display_master_coordinates(master, getattr(section, role))
                assert xi.shape == getattr(section, role).r.shape
                assert np.isfinite(xi).all() and xi.min() >= 0 and xi.max() <= 1
                provenance = curve_provenance(master, section.span)
                if case == 'trim' and section.span > 0:
                    assert provenance.source_span_kind == 'original_geometry'
                    assert np.max(provenance.source_span) < section.span


@pytest.mark.parametrize('case', ['Impeller', 'Diffuser', 'RC', 'rake_gap_splitter'])
def test_real_display_lines_are_measurable_without_modifying_geometry(case):
    geometry = generated_case(case)
    for sections in (geometry.sections, geometry.splitter_sections or []):
        if not sections:continue
        for role in ('le', 'ps', 'te', 'ss'):
            rows = [getattr(s, 'master_'+role) for s in sections]
            before = [curve.xyz.copy() for curve in rows]
            spline = fit_surface_spline(before, 33, [cad_curve_coordinates(c) for c in rows], [s.span for s in sections])
            result = compare_preview_to_spline(sections, role, spline, [0., .35, .5, 1.])
            assert np.isfinite(result['max_mm']) and result['max_mm'] >= result['rms_mm']
            for curve, original in zip(rows, before):np.testing.assert_array_equal(curve.xyz, original)
