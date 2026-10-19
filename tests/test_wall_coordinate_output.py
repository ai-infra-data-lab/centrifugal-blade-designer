"""Wall meridians, grouping and tab-separated TXT, independent of Qt."""
from copy import deepcopy
from dataclasses import replace
import csv
import io
from types import SimpleNamespace
import numpy as np
import pytest
from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions, prepare_coordinate_csv, export_coordinate_csv, COORDINATES
from blade_designer.fileio.geometry_source import geometry_source
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.row_domain import preview_wall_chunks
from blade_designer.models.parameters import SplitterParameters, ImpellerTrimParameters, TipClearanceParameters
from test_impeller_te_rake import radial_parameters


def read(data, extension):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig')), delimiter='\t' if extension == 'txt' else ','))


@pytest.fixture(scope='module')
def example():
    p = radial_parameters()
    p.splitter = SplitterParameters()
    return generate_impeller(p), geometry_source(p, 'meridional_3d')


@pytest.mark.parametrize('extension', ['csv', 'txt'])
@pytest.mark.parametrize('layout', ['combined', 'together', 'separate'])
@pytest.mark.parametrize('blades', [False, True])
def test_combined_and_separate_data_match_for_blades_and_both_walls(example, extension, layout, blades, tmp_path):
    g, source = example
    options = CoordinateCsvOptions(('z_mm', 'r_mm', 'theta_rad', 'rtheta_mm'), include_blades=blades,
                                   include_hub=True, include_shroud=True, wall_layout=layout, extension=extension)
    contents = prepare_coordinate_csv(g, source, options)
    expected = prepare_coordinate_csv(g, source, replace(options, wall_layout='combined'))
    rows = [r for data in contents.values() for r in read(data, extension)]
    assert rows == read(expected['coordinates.' + extension], extension)
    assert all(name.endswith('.' + extension) for name in contents)
    assert len(contents) == (1 if layout == 'combined' else int(blades) + (1 if layout == 'together' else 2))
    target = tmp_path / ('bundle' if options.requires_directory else 'single.' + extension)
    files = export_coordinate_csv(target, g, source, options)
    assert [file.read_bytes() for file in files] == list(contents.values())
    if extension == 'txt':
        assert '\t' in next(iter(contents.values())).decode('utf-8-sig').splitlines()[0]


@pytest.mark.parametrize('extension', ['csv', 'txt'])
@pytest.mark.parametrize('layout', ['together', 'separate'])
def test_span_split_also_separates_walls_and_preserves_group_identity(example, extension, layout):
    g, source = example
    options = CoordinateCsvOptions(split_spans=True, include_hub=True, include_shroud=True,
                                   wall_layout=layout, extension=extension)
    contents = prepare_coordinate_csv(g, source, options)
    assert len(contents) == len(g.sections) + len(g.splitter_sections) + (1 if layout == 'together' else 2)
    wall_names = ['walls.' + extension] if layout == 'together' else ['hub.' + extension, 'shroud.' + extension]
    walls = [r for name in wall_names for r in read(contents[name], extension)]
    assert {row['blade_set'] for row in walls} == {'hub', 'shroud'}
    assert all(row['span'] == '' and row['m_blade_norm'] == '' for row in walls)


@pytest.mark.parametrize('split', [False, True])
def test_blades_only_txt_has_same_values_as_csv_and_txt_filenames(example, split, tmp_path):
    g, source = example
    options = CoordinateCsvOptions(('r_mm', 'theta_deg', 'z_mm'), split_spans=split)
    csv_data = prepare_coordinate_csv(g, source, options)
    txt_options = replace(options, extension='txt')
    txt_data = prepare_coordinate_csv(g, source, txt_options)
    assert [read(data, 'txt') for data in txt_data.values()] == [read(data, 'csv') for data in csv_data.values()]
    files = export_coordinate_csv(tmp_path / ('bundle' if split else 'blades.txt'), g, source, txt_options)
    assert all(path.suffix == '.txt' for path in files)


@pytest.mark.parametrize('wall', ['hub', 'shroud'])
def test_wall_only_coordinates_theta_zero_and_separate_owned_runs(example, wall):
    g, source = example
    chunks = {wall: [SimpleNamespace(r=np.array([2., 3.]), z=np.array([1., 4.])),
                     SimpleNamespace(r=np.array([7., 9.]), z=np.array([10., 11.]))]}
    options = CoordinateCsvOptions(tuple(reversed(COORDINATES)), include_blades=False,
                                   include_hub=wall == 'hub', include_shroud=wall == 'shroud')
    contents = prepare_coordinate_csv(g, source, options, wall_chunks=chunks)
    rows = read(contents['coordinates.csv'], 'csv')
    assert [row['segment'] for row in rows] == [wall.upper() + '_001'] * 2 + [wall.upper() + '_002'] * 2
    assert [row['index'] for row in rows] == ['0', '1', '0', '1']
    np.testing.assert_array_equal([[float(row[c]) for c in ('r_mm', 'z_mm')] for row in rows], [[2, 1], [3, 4], [7, 10], [9, 11]])
    assert all(float(row['theta_deg']) == float(row['theta_rad']) == float(row['rtheta_mm']) == float(row['y_mm']) == 0 for row in rows)
    assert all(row['x_mm'] == row['r_mm'] for row in rows)


@pytest.mark.parametrize('variant', ['base', 'clearance', 'trim'])
def test_walls_follow_generated_casing_not_clearance_tip_and_keep_design(variant):
    p = radial_parameters()
    if variant == 'clearance':
        p.tip_clearance = TipClearanceParameters(.5, 1.)
    elif variant == 'trim':
        p.impeller_trim = ImpellerTrimParameters(shroud_area_cut_percent=5.)
    before = deepcopy(p)
    g = generate_impeller(p)
    source = geometry_source(p, 'meridional_3d', variant='derived' if g.trim_report else 'base')
    chunks = preview_wall_chunks(p, g, p.active_blade_row)
    options = CoordinateCsvOptions(('r_mm', 'z_mm'), include_blades=False, include_shroud=True)
    rows = read(prepare_coordinate_csv(g, source, options, wall_chunks=chunks)['coordinates.csv'], 'csv')
    np.testing.assert_allclose([[float(row[k]) for k in ('r_mm', 'z_mm')] for row in rows],
                               np.column_stack((g.shroud.r, g.shroud.z)), rtol=1e-13, atol=1e-12)
    assert p == before


@pytest.mark.parametrize('problem', ['empty', 'nonfinite', 'negative'])
def test_invalid_wall_protects_existing_file_and_new_bundle(example, problem, tmp_path):
    g, source = example
    chunks = {'hub': [g.hub], 'shroud': [SimpleNamespace(r=np.array([1., 2.]), z=np.array([0., 1.]))]}
    if problem == 'empty':
        chunks['shroud'] = []
    elif problem == 'nonfinite':
        chunks['shroud'][0].z[-1] = np.nan
    else:
        chunks['shroud'][0].r[-1] = -1.
    options = CoordinateCsvOptions(include_hub=True, include_shroud=True)
    target = tmp_path / 'old.txt'
    target.write_bytes(b'previous')
    with pytest.raises(ValueError):
        export_coordinate_csv(target, g, source, replace(options, extension='txt'), wall_chunks=chunks)
    with pytest.raises(ValueError):
        export_coordinate_csv(tmp_path / 'bundle', g, source, replace(options, wall_layout='separate'), wall_chunks=chunks)
    assert target.read_bytes() == b'previous' and not (tmp_path / 'bundle').exists()


@pytest.mark.parametrize('changes', [dict(include_blades=False), dict(extension='exe'), dict(wall_layout='other'),
    dict(include_hub=True, split_spans=True), dict(include_blades=False, include_hub=True, split_spans=True)])
def test_invalid_output_options_are_rejected(changes):
    with pytest.raises(ValueError):
        CoordinateCsvOptions(**changes).validate()
