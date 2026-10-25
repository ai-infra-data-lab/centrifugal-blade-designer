from dataclasses import replace
import csv
import hashlib
import json
from pathlib import Path
import pytest

from blade_designer.fileio.project_io import load_project
from blade_designer.fileio.coordinate_study import (queue_study, export_study, read_study,
    import_results, rank_results, project_hash)
from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions, prepare_coordinate_csv
from blade_designer.optimization.coordinate_parameters import CoordinateStudy
from blade_designer.models.blade_rows import row_parameters
from blade_designer.models.geometry_source import GeometrySource
from blade_designer.geometry.geometry_3d import generate_impeller, generate_diffuser_3d
from blade_designer.geometry.row_domain import preview_wall_chunks

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def study():
    return CoordinateStudy(load_project(ROOT / 'blade_designer/defaults/default_project.json'))


def make_run(tmp_path, study, count=0):
    variable = replace(study.variables[0], lower=-.1, upper=.1, enabled=True)
    options = CoordinateCsvOptions(columns=('r_mm', 'theta_rad', 'z_mm'), split_spans=True,
                                   include_hub=True, include_shroud=True, wall_layout='separate', extension='txt')
    job = queue_study(study, [variable], count, 7, options, tmp_path / 'run', job_directory=tmp_path / 'job')
    report = export_study(job)
    loaded, manifest = read_study(tmp_path / 'run')
    assert loaded.baseline == study.baseline and report['overall'] == 'PASS'
    return job, manifest, options


def test_baseline_all_rows_matches_existing_coordinate_export_bytes(tmp_path, study):
    before = project_hash(study.baseline)
    job, manifest, options = make_run(tmp_path, study, 1)
    assert len(manifest['cases']) == 2 and manifest['cases'][0]['values'] == {}
    assert project_hash(study.baseline) == before
    candidate = study.baseline
    for i, row in enumerate(candidate.blade_rows):
        params = row_parameters(candidate, row)
        geometry = generate_impeller(params) if row.kind == 'impeller' else generate_diffuser_3d(params)
        source = GeometrySource(row.identifier, row.name, row.kind, 'meridional_3d', 'coordinate_study', before)
        expected = prepare_coordinate_csv(geometry, source, options, 15,
                                         wall_chunks=preview_wall_chunks(candidate, geometry, row.identifier))
        for name, data in expected.items():
            assert (tmp_path / 'run' / 'case_0000' / f'row_{i + 1:03d}' / name).read_bytes() == data
    assert manifest['cad'] == 'NOT_EVALUATED' and manifest['cfd'] == 'NOT_EXECUTED'


def test_existing_output_and_changed_snapshot_are_protected(tmp_path, study):
    job, manifest, _ = make_run(tmp_path, study)
    protected = (tmp_path / 'run/manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        export_study(job)
    assert (tmp_path / 'run/manifest.json').read_bytes() == protected
    (job / 'snapshot.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot'):
        export_study(job)


def test_changed_output_rejected_on_resume(tmp_path, study):
    _, manifest, _ = make_run(tmp_path, study)
    name = next(iter(manifest['cases'][0]['sha256']))
    (tmp_path / 'run' / name).write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        read_study(tmp_path / 'run')


@pytest.mark.parametrize('version',[None,'older-geometry'])
def test_previous_geometry_study_cannot_reuse_external_evaluation(tmp_path,study,version):
    _,manifest,_=make_run(tmp_path,study)
    payloads={name:(tmp_path/'run'/name).read_bytes() for name in manifest['cases'][0]['sha256']}
    if version is None:manifest.pop('coordinate_geometry_version')
    else:manifest['coordinate_geometry_version']=version
    path=tmp_path/'run/manifest.json';path.write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError,match='geometry version'):read_study(tmp_path/'run')
    assert all((tmp_path/'run'/name).read_bytes()==data for name,data in payloads.items())


def test_queued_previous_geometry_job_is_rejected_before_publication(tmp_path,study):
    job=queue_study(study,[],0,1,CoordinateCsvOptions(),tmp_path/'run',job_directory=tmp_path/'job')
    path=job/'request.json';request=json.loads(path.read_text(encoding='utf-8'))
    request.pop('coordinate_geometry_version');path.write_text(json.dumps(request),encoding='utf-8')
    with pytest.raises(ValueError,match='geometry version'):export_study(job)
    assert not (tmp_path/'run').exists()


def write_results(path, manifest, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['run_id', 'candidate_id', 'candidate_hash', 'status', 'efficiency', 'pressure_ratio'])
        for index, status, efficiency, pressure in rows:
            case = manifest['cases'][index]
            writer.writerow([manifest['run_id'], case['candidate_id'], case['candidate_hash'],
                             status, efficiency, pressure])


def test_external_ranking_constraints_and_pending_no_fake_scores(tmp_path, study):
    _, manifest, _ = make_run(tmp_path, study, 2)
    path = tmp_path / 'results.csv'
    write_results(path, manifest, [(0, 'success', .8, 2), (1, 'success', .9, 1), (2, 'failed', '', '')])
    results = import_results(path, manifest)
    assert rank_results(results, 'efficiency') == ['case_0001', 'case_0000']
    assert rank_results(results, 'efficiency', constraints={'pressure_ratio': (1.5, 3)}) == ['case_0000']
    assert rank_results(results, 'efficiency', maximize=False)[0] == 'case_0000'
    assert results['case_0002']['metrics']['efficiency'] is None


@pytest.mark.parametrize('status,value', [('success', 'NaN'), ('success', 'inf'),
                                         ('failed', '0'), ('pending', '.8'), ('bogus', '')])
def test_bad_external_results_rejected(tmp_path, study, status, value):
    _, manifest, _ = make_run(tmp_path, study)
    path = tmp_path / 'results.csv'
    write_results(path, manifest, [(0, status, value, '')])
    with pytest.raises(ValueError):
        import_results(path, manifest)


def test_wrong_run_duplicate_and_hash_rejected(tmp_path, study):
    _, manifest, _ = make_run(tmp_path, study)
    path = tmp_path / 'results.csv'
    write_results(path, manifest, [(0, 'success', .8, 2), (0, 'success', .9, 2)])
    with pytest.raises(ValueError):
        import_results(path, manifest)
    write_results(path, manifest, [(0, 'success', .8, 2)])
    text = path.read_text(encoding='utf-8-sig')
    path.write_text(text.replace(manifest['run_id'], 'wrong'), encoding='utf-8-sig')
    with pytest.raises(ValueError):
        import_results(path, manifest)


def test_failed_mapping_has_no_partial_coordinates_and_study_can_resume(tmp_path, study):
    variable = next(v for v in study.variables if 'Δturn' in v.label)
    variable = replace(variable, enabled=True, lower=-999, upper=-998)
    job = queue_study(study, [variable], 1, 0, CoordinateCsvOptions(), tmp_path / 'run',
                      job_directory=tmp_path / 'job')
    export_study(job)
    _, manifest = read_study(tmp_path / 'run')
    assert manifest['cases'][0]['status'] == 'READY_FOR_EXTERNAL'
    assert manifest['cases'][1]['status'] == 'FAILED'
    assert not (tmp_path / 'run/case_0001').exists()


def test_destination_created_during_generation_is_not_replaced(tmp_path, study, monkeypatch):
    from blade_designer.fileio import coordinate_study as module
    job = queue_study(study, [], 0, 0, CoordinateCsvOptions(), tmp_path / 'run',
                      job_directory=tmp_path / 'job')
    original = module._write_case_files
    def write(stage, contents):
        original(stage, contents)
        if 'manifest.json' in contents:
            (tmp_path / 'run').mkdir()
            (tmp_path / 'run/marker').write_text('external data')
    monkeypatch.setattr(module, '_write_case_files', write)
    with pytest.raises(FileExistsError):
        export_study(job)
    assert (tmp_path / 'run/marker').read_text() == 'external data'
    assert not (tmp_path / 'run/manifest.json').exists()


def test_coordinate_export_does_not_require_cad_runtime(tmp_path, study, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'OCP', None)
    monkeypatch.setitem(sys.modules, 'blade_designer.cad.occt_backend', None)
    make_run(tmp_path, study)


def test_import_duplicate_metric_columns_and_changed_candidate_hash_rejected(tmp_path, study):
    _, manifest, _ = make_run(tmp_path, study)
    path = tmp_path / 'results.csv'
    write_results(path, manifest, [(0, 'success', .8, 2)])
    text = path.read_text(encoding='utf-8-sig')
    path.write_text(text.replace('pressure_ratio', 'efficiency'), encoding='utf-8-sig')
    with pytest.raises(ValueError):
        import_results(path, manifest)
    write_results(path, manifest, [(0, 'success', .8, 2)])
    path.write_text(path.read_text(encoding='utf-8-sig').replace(manifest['cases'][0]['candidate_hash'], 'wrong'),
                    encoding='utf-8-sig')
    with pytest.raises(ValueError):
        import_results(path, manifest)


def test_repeated_batches_have_distinct_run_identity(tmp_path, study):
    _, first, _ = make_run(tmp_path, study)
    second_job = queue_study(study, [], 0, 0, CoordinateCsvOptions(), tmp_path / 'second',
                             job_directory=tmp_path / 'second-job')
    export_study(second_job)
    _, second = read_study(tmp_path / 'second')
    assert first['run_id'] != second['run_id']
    path = tmp_path / 'results.csv'
    write_results(path, first, [(0, 'success', .8, 2)])
    with pytest.raises(ValueError):
        import_results(path, second)


def test_external_condition_id_cannot_be_mixed(tmp_path, study):
    job = queue_study(study, [], 0, 0, CoordinateCsvOptions(), tmp_path / 'run',
                      job_directory=tmp_path / 'job', evaluation_context='rpm10000-inlet-A')
    export_study(job)
    _, manifest = read_study(tmp_path / 'run')
    template = tmp_path / 'run/external_results_template.csv'
    text = template.read_text(encoding='utf-8-sig')
    path = tmp_path / 'results.csv'
    path.write_text(text.replace('pending,', 'success,.8'), encoding='utf-8-sig')
    assert import_results(path, manifest)['case_0000']['metrics']['efficiency'] == .8
    path.write_text(text.replace('rpm10000-inlet-A', 'other-condition'), encoding='utf-8-sig')
    with pytest.raises(ValueError, match='condition'):
        import_results(path, manifest)
