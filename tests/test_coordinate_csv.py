"""Analytic coordinate/unit checks and whole-output protection."""
from copy import deepcopy
from dataclasses import replace
import csv
import io
from types import SimpleNamespace
import numpy as np
import pytest
from blade_designer.fileio.coordinate_csv import (
    CoordinateCsvOptions, prepare_coordinate_csv, export_coordinate_csv, COORDINATES)
from blade_designer.fileio.row_xyz_csv import prepare_row_xyz_csv
from blade_designer.fileio.geometry_source import geometry_source
from blade_designer.geometry.geometry_3d import generate_impeller, generate_diffuser_3d
from blade_designer.models.parameters import SplitterParameters, TipClearanceParameters, ImpellerTrimParameters
from blade_designer.models.geometry_3d import Curve3D
from test_impeller_te_rake import radial_parameters


def read(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))


@pytest.fixture(scope='module')
def example():
    p = radial_parameters()
    p.splitter = SplitterParameters()
    return generate_impeller(p), geometry_source(p, 'meridional_3d')


def test_analytic_axes_continuous_theta_and_rtheta_not_degrees():
    p = radial_parameters()
    theta = np.array([0., np.pi / 2, -np.pi / 2, 5 * np.pi / 2])
    r = np.array([2., 3., 4., 5.])
    curve = Curve3D(r, theta, np.array([1., 2., 3., 4.]))
    section = SimpleNamespace(span=0., **{'master_' + role: curve for role in ('le', 'ps', 'te', 'ss')})
    geometry = SimpleNamespace(sections=[section], splitter_sections=None)
    before = curve.xyz.copy()
    options = CoordinateCsvOptions(tuple(reversed(COORDINATES)), include_metadata=False)
    payload = prepare_coordinate_csv(geometry, geometry_source(p, 'meridional_3d'), options)['coordinates.csv']
    rows = read(payload)
    assert list(rows[0]) == list(reversed(COORDINATES))
    np.testing.assert_allclose([float(row['theta_deg']) for row in rows[:4]], [0., 90., -90., 450.])
    np.testing.assert_allclose([float(row['rtheta_mm']) for row in rows[:4]], r * theta)
    np.testing.assert_allclose([float(row['r_mm']) for row in rows[:4]], r)
    np.testing.assert_allclose([[float(row[c]) for c in ('x_mm', 'y_mm', 'z_mm')] for row in rows[:4]],
                               [[2., 0., 1.], [0., 3., 2.], [0., -4., 3.], [0., 5., 4.]], atol=1e-14)
    np.testing.assert_array_equal(curve.xyz, before)


def test_explicit_legacy_column_set_has_identical_bytes(example):
    g, source = example
    options = CoordinateCsvOptions(('x_mm', 'y_mm', 'z_mm', 'r_mm', 'theta_deg'))
    assert prepare_coordinate_csv(g, source, options)['coordinates.csv'] == prepare_row_xyz_csv(g, source)


@pytest.mark.parametrize('columns', [('z_mm', 'r_mm', 'theta_rad'), ('rtheta_mm', 'z_mm'), ('theta_deg',)])
@pytest.mark.parametrize('metadata', [False, True])
def test_order_subset_and_span_split_equal_combined_rows(example, columns, metadata, tmp_path):
    g, source = example
    options = CoordinateCsvOptions(columns, include_metadata=metadata)
    unified = read(prepare_coordinate_csv(g, source, options)['coordinates.csv'])
    target = tmp_path / 'bundle'
    files = export_coordinate_csv(target, g, source, replace(options, split_spans=True))
    assert len(files) == len(g.sections) + len(g.splitter_sections)
    split = [row for file in files for row in read(file.read_bytes())]
    assert split == unified
    assert files[0].name.startswith('main_span_001_0')
    assert any(f.name.startswith('splitter_span_') for f in files)


@pytest.mark.parametrize('columns', [(), ('bad',), ('r_mm', 'r_mm')])
def test_bad_columns_never_touch_destination(example, columns, tmp_path):
    g, source = example
    target = tmp_path / 'keep.csv'
    target.write_bytes(b'previous')
    with pytest.raises(ValueError):
        export_coordinate_csv(target, g, source, CoordinateCsvOptions(columns))
    assert target.read_bytes() == b'previous'


@pytest.mark.parametrize('bad', ['main', 'splitter', 'span', 'streamwise', 'engine', 'empty', 'theta', 'radius'])
def test_invalid_last_curve_or_source_protects_all_files(example, bad, tmp_path):
    g, source = example
    g = deepcopy(g)
    if bad in ('main', 'splitter'):
        sections = g.sections if bad == 'main' else g.splitter_sections
        sections[-1].master_ss.z[-1] = float('nan')
    elif bad == 'span':
        g.sections[-1].span = g.sections[0].span
    elif bad == 'streamwise':
        g.sections[-1].master_ss.m_blade_norm = np.array([0.])
    elif bad == 'engine':
        source = replace(source, engine='legacy_radial_2d')
    elif bad == 'theta':
        g.sections[-1].master_ss.theta_rad[-1] = float('inf')
    elif bad == 'radius':
        g.sections[-1].master_ss.r[-1] = -1.
    else:
        g.sections = []
    target = tmp_path / 'keep.csv'
    target.write_bytes(b'previous')
    with pytest.raises(ValueError):
        export_coordinate_csv(target, g, source)
    with pytest.raises(ValueError):
        export_coordinate_csv(tmp_path / 'new_bundle', g, source, CoordinateCsvOptions(split_spans=True))
    assert target.read_bytes() == b'previous' and not (tmp_path / 'new_bundle').exists()


def test_single_install_failure_and_bundle_failure_preserve_outputs(example, tmp_path, monkeypatch):
    from blade_designer.fileio import coordinate_csv
    g, source = example
    target = tmp_path / 'keep.csv'
    target.write_bytes(b'previous')
    with monkeypatch.context() as patch:
        patch.setattr(coordinate_csv.os, 'replace', lambda *args: (_ for _ in ()).throw(PermissionError('locked')))
        with pytest.raises(PermissionError):
            export_coordinate_csv(target, g, source)
    assert target.read_bytes() == b'previous'
    assert list(tmp_path.iterdir()) == [target]
    def fail(stage, contents):
        (stage / 'partial.csv').write_bytes(b'partial')
        raise OSError('disk full')
    monkeypatch.setattr(coordinate_csv, '_write_case_files', fail)
    with pytest.raises(OSError, match='disk full'):
        export_coordinate_csv(tmp_path / 'bundle', g, source, CoordinateCsvOptions(split_spans=True))
    assert not (tmp_path / 'bundle').exists()
    assert target.read_bytes() == b'previous'


def test_existing_bundle_and_unrelated_files_are_preserved(example, tmp_path):
    g, source = example
    target = tmp_path / 'bundle'
    target.mkdir()
    original = target / 'user.txt'
    original.write_bytes(b'user')
    with pytest.raises(FileExistsError):
        export_coordinate_csv(target, g, source, CoordinateCsvOptions(split_spans=True))
    assert list(target.iterdir()) == [original] and original.read_bytes() == b'user'


@pytest.mark.parametrize('kind', ['impeller', 'diffuser'])
@pytest.mark.parametrize('variant', ['base', 'clearance', 'trim'])
def test_selected_coordinates_follow_actual_generated_sections(kind, variant):
    p = radial_parameters()
    if variant == 'clearance':
        p.tip_clearance = TipClearanceParameters(.5, 1.)
    if variant == 'trim':
        p.impeller_trim = ImpellerTrimParameters(shroud_area_cut_percent=5.)
    before = deepcopy(p)
    g = generate_impeller(p) if kind == 'impeller' else generate_diffuser_3d(p)
    source = geometry_source(p, 'meridional_3d', kind=kind, variant='derived' if g.trim_report else 'base')
    rows = read(prepare_coordinate_csv(g, source, CoordinateCsvOptions(COORDINATES))['coordinates.csv'])
    ps = [row for row in rows if row['span'] == '1' and row['segment'] == 'PS']
    c = g.sections[-1].master_ps
    np.testing.assert_allclose([[float(row[k]) for k in ('r_mm', 'theta_rad', 'z_mm')] for row in ps],
                               np.column_stack((c.r, c.theta_rad, c.z)), rtol=1e-13, atol=1e-12)
    assert p == before
