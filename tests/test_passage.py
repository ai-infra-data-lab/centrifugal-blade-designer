"""Analytic annular/planar passages, independent of historical fixtures."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.passage import calculate_passages, closest_polylines
from blade_designer.geometry.meridional_segments import generate_meridional
from blade_designer.models.geometry_3d import Curve3D, SectionGeometry3D, ImpellerGeometry
from blade_designer.models.meridional import MeridionalCurveParameters, LineSegmentParameters


def section(span, start, end, center=0., half=.01, axial=False):
    def curve(m, theta):
        m, theta = np.broadcast_arrays(m, theta)
        return Curve3D(np.full(m.shape, 50+20*span) if axial else m,
                       theta.copy(), m if axial else np.full(m.shape, 20*span))
    m = np.linspace(start, end, 17)
    camber = curve(m, center)
    ps, ss = curve(m, center+half), curve(m, center-half)
    le = curve(start, np.linspace(center-half, center+half, 11))
    te = curve(end, np.linspace(center+half, center-half, 11))
    return SectionGeometry3D(span, camber, ps, ss, le, te, ps, ss, le, te,
                             m, np.zeros(len(m)), np.full(len(m), 2*half))


def radial(split=False, sign=1, offset=.35, half=.01):
    hub = generate_meridional(MeridionalCurveParameters(0, 40, 90, [LineSegmentParameters(70)]))
    shroud = generate_meridional(MeridionalCurveParameters(20, 40, 90, [LineSegmentParameters(70)]))
    main = [section(s, 50, 100, half=half) for s in (0., .5, 1.)]
    splitter = [section(s, 70, 100, sign*2*np.pi/12*offset, .005) for s in (0., .5, 1.)] if split else None
    return ImpellerGeometry(hub, shroud, main, splitter)


def test_exact_polyline_distance_not_nearest_vertices():
    a = np.array([[-10, 0, 1], [10, 0, 1.]])
    b = np.array([[0, -10, 4], [0, 10, 4.]])
    width, p, q = closest_polylines(a, b)
    assert width == pytest.approx(3)
    np.testing.assert_allclose(p, [0, 0, 1])
    np.testing.assert_allclose(q, [0, 0, 4])
    assert closest_polylines(a, b-[0, 0, 3])[0] == pytest.approx(0)
    assert closest_polylines(a[:1].repeat(2, axis=0), b)[0] == pytest.approx(np.sqrt(109))


def test_radial_gross_net_and_exact_planar_throat_strip():
    row = radial()
    before = deepcopy(row.sections[0].master_ps.xyz)
    result = calculate_passages(row, 12)
    assert not result.errors
    assert len(result.stations) > 20
    pitch = 2*np.pi/12
    for cut in result.stations:
        r = 40+70*cut.m_flow_norm
        assert cut.gross_annulus == pytest.approx(2*np.pi*r*20)
        assert cut.main_reference == pytest.approx(r*(pitch-.02)*20)
        assert cut.net_per_pitch == cut.main_reference
        assert cut.main_splitter is None and cut.splitter_main is None
    throat, = result.throats
    exact = 100*np.sin((pitch-.02)/2)
    np.testing.assert_allclose(throat.widths, exact, atol=1e-10)
    assert throat.strip_area == pytest.approx(exact*20)
    assert not throat.reference_only
    np.testing.assert_array_equal(row.sections[0].master_ps.xyz, before)


@pytest.mark.parametrize('sign', [-1, 1])
def test_splitter_both_passages_and_upstream_area_are_separate(sign):
    result = calculate_passages(radial(True, sign), 12, sign)
    assert not result.errors
    pitch = 2*np.pi/12
    before, after = [], []
    for cut in result.stations:
        r = 40+70*cut.m_flow_norm
        if r < 70-1e-8:
            before.append(cut)
            assert cut.main_splitter is None and cut.splitter_main is None
            assert cut.net_per_pitch == cut.main_reference
        else:
            after.append(cut)
            assert cut.main_splitter == pytest.approx(r*(pitch*.35-.015)*20)
            assert cut.splitter_main == pytest.approx(r*(pitch*.65-.015)*20)
            assert cut.main_splitter+cut.splitter_main == pytest.approx(cut.net_per_pitch)
            assert cut.net_per_pitch == pytest.approx(r*(pitch-.03)*20)
    assert before and after
    mm, ms, sm = result.throats
    assert mm.reference_only and not ms.reference_only and not sm.reference_only
    assert ms.minimum_width == pytest.approx(70*np.sin(pitch*.35-.015))
    assert sm.minimum_width == pytest.approx(70*np.sin(pitch*.65-.015))
    assert ms.strip_area == pytest.approx(ms.minimum_width*20)
    assert sm.strip_area == pytest.approx(sm.minimum_width*20)


def test_axial_annulus_area_and_three_dimensional_throat():
    hub = generate_meridional(MeridionalCurveParameters(0, 50, 0, [LineSegmentParameters(100)]))
    shroud = generate_meridional(MeridionalCurveParameters(0, 70, 0, [LineSegmentParameters(100)]))
    row = ImpellerGeometry(hub, shroud, [section(s, 10, 90, axial=True) for s in (0., 1.)])
    result = calculate_passages(row, 12)
    assert not result.errors
    for cut in result.stations:
        assert cut.gross_annulus == pytest.approx(np.pi*(70**2-50**2))
        assert cut.net_per_pitch == pytest.approx((2*np.pi/12-.02)*(70**2-50**2)/2)
    assert result.throats[0].minimum_width == pytest.approx(50*(2*np.pi/12-.02))
    assert 'Developed' in result.throats[0].method
    assert result.throats[0].strip_area == pytest.approx((2*np.pi/12-.02)*(70**2-50**2)/2)


def test_cone_development_has_analytic_intrinsic_distance():
    from blade_designer.geometry.passage import _section_gap
    s = section(0., 50, 100)
    for curve in (s.camber, s.master_le, s.master_ps, s.master_te, s.master_ss):
        curve.z[:] = 2*(curve.r-50)
    pitch = 2*np.pi/12
    width, _, _, method = _section_gap(s, s, pitch)
    k = 1/np.sqrt(5)
    assert width == pytest.approx(100/k*np.sin(k*(pitch-.02)/2))
    assert 'Developed' in method


def test_curved_wall_is_explicitly_a_chord_lower_bound():
    from blade_designer.geometry.passage import _section_gap, _contour, _rotate
    s = section(0., 50, 100)
    for curve in (s.camber, s.master_le, s.master_ps, s.master_te, s.master_ss):
        curve.z[:] = (curve.r-50)**2/100
    angle = 2*np.pi/12
    measured, _, _, method = _section_gap(s, s, angle)
    assert measured == closest_polylines(_contour(s), _rotate(_contour(s), angle))[0]
    assert 'lower-bound' in method


def test_actual_default_curved_wall_cuts_have_no_sampling_gaps():
    from pathlib import Path
    from blade_designer.fileio.project_io import load_project
    from blade_designer.models.blade_rows import row_parameters
    from blade_designer.geometry.geometry_3d import generate_impeller
    from blade_designer.models.parameters import SplitterParameters
    p = load_project(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json')
    p = row_parameters(p, p.blade_rows[0])
    p.splitter = SplitterParameters()
    result = calculate_passages(generate_impeller(p), p.geometry.vane_count, points=101)
    assert result.stations and not result.errors
    assert len(result.throats) == 3


def test_displaced_boundary_is_not_silently_snapped_to_wall():
    row = radial()
    for curve in (row.sections[0].camber, row.sections[0].master_le, row.sections[0].master_ps,
                  row.sections[0].master_te, row.sections[0].master_ss):
        curve.z[:] += .5
    result = calculate_passages(row, 12)
    assert not result.stations
    assert any('displaced beyond' in error for error in result.errors)


@pytest.mark.parametrize('count', [True, 1, 0, 2.5])
def test_no_invalid_blade_count(count):
    with pytest.raises(ValueError, match='at least two'):
        calculate_passages(radial(), count)


def test_overlapping_pitch_is_not_reported_as_valid_area():
    result = calculate_passages(radial(half=.3), 12)
    assert not result.stations
    assert any('blocks/overlaps' in message for message in result.errors)
    assert not result.throats


def test_real_mapped_splitter_uses_master_curves_not_output_density():
    from blade_designer.geometry.geometry_3d import generate_impeller
    from blade_designer.models.parameters import SplitterParameters
    from test_impeller_te_rake import radial_parameters
    p = radial_parameters()
    p.impeller_te_rake_deg = 15
    p.splitter = SplitterParameters()
    first = calculate_passages(generate_impeller(p), p.geometry.vane_count, points=51)
    p.output_points.ps_points = 17
    p.output_points.ss_points = 19
    second = calculate_passages(generate_impeller(p), p.geometry.vane_count, points=51)
    assert first.stations and len(first.throats) == 3
    assert first.stations == second.stations
    for a, b in zip(first.throats, second.throats):
        np.testing.assert_array_equal(a.widths, b.widths)
        assert a.strip_area == b.strip_area
