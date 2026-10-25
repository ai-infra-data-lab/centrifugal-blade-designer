"""Coordinate-only studies and external results. No CAD, meshing or CFD execution."""
from dataclasses import asdict
import csv
import hashlib
import io
import json
from pathlib import Path
import uuid

from .preview_job import ROOT, snapshot_text
from .project_io import _decode_v03
from .coordinate_csv import CoordinateCsvOptions, prepare_coordinate_csv
from .case_publish import staged_case, _write_case_files
from ..optimization.coordinate_parameters import CoordinateStudy, CoordinateVariable, sample_candidates
from ..geometry.edge_positioning import COORDINATE_GEOMETRY_VERSION


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_sha256(path):
    """Hash imported results with bounded memory, including large legacy CSVs."""
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def project_hash(project):
    return digest(snapshot_text(project).encode('utf-8'))


def queue_study(study, variables, count, seed, options, output, center=None, job_directory=None,
                evaluation_context='', proposal=None):
    study.validate_variables(variables)
    options.validate()
    if not isinstance(evaluation_context, str) or len(evaluation_context) > 512:
        raise ValueError('Use a textual external analysis-condition ID of at most 512 characters.')
    frozen = None
    if proposal is not None:
        if center is not None:
            raise ValueError('RBF proposals and Local LHS are separate sampling methods.')
        from .coordinate_proposal import freeze_proposal
        frozen = freeze_proposal(proposal, count)
    vectors = sample_candidates(study, variables, 0 if frozen else count, seed, center)
    job = Path(job_directory) if job_directory else ROOT / 'artifacts' / 'coordinate-studies' / uuid.uuid4().hex
    job.mkdir(parents=True, exist_ok=False)
    data = snapshot_text(study.baseline).encode('utf-8')
    request = {'snapshot_hash': digest(data), 'row_ids': study.row_ids,
               'coordinate_geometry_version': COORDINATE_GEOMETRY_VERSION,
               'variables': [asdict(v) for v in variables], 'vectors': vectors,
               'options': asdict(options), 'output': str(Path(output).resolve()),
               'run_id': uuid.uuid4().hex, 'seed': seed,
               'evaluation_context': evaluation_context,
               'sampling': 'local_lhs' if center is not None else 'lhs'}
    (job / 'snapshot.json').write_bytes(data)
    if frozen:
        request['proposal'] = frozen[0]
        request['sampling'] = 'rbf_external'
        (job / 'external-results.csv').write_bytes(frozen[1])
    (job / 'request.json').write_bytes(json_bytes(request))
    return job


def read_study(directory):
    directory = Path(directory)
    if (directory / 'manifest.json').stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Study manifest size limit exceeded.')
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if (not isinstance(manifest, dict) or manifest.get('schema') != 'coordinate-study-1'
            or not isinstance(manifest.get('run_id'), str) or not manifest['run_id']
            or not isinstance(manifest.get('variables'), list)
            or not isinstance(manifest.get('row_ids'), list) or not isinstance(manifest.get('options'), dict)):
        raise ValueError('Unsupported coordinate-study manifest.')
    if manifest.get('coordinate_geometry_version') != COORDINATE_GEOMETRY_VERSION:
        raise ValueError('Study geometry version differs. Regenerate coordinates and reevaluate external results.')
    if (directory / 'baseline.json').stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Baseline snapshot size limit exceeded.')
    data = (directory / 'baseline.json').read_bytes()
    if digest(data) != manifest['baseline_hash']:
        raise ValueError('Baseline snapshot hash mismatch.')
    study = CoordinateStudy(_decode_v03(json.loads(data), row_snapshot=True), manifest['row_ids'])
    try:
        variables = [CoordinateVariable(**v) for v in manifest['variables']]
        options = dict(manifest['options'])
        options['columns'] = tuple(options['columns'])
        CoordinateCsvOptions(**options).validate()
    except TypeError as exc:
        raise ValueError('Malformed study variables.') from exc
    study.validate_variables(variables)
    cases = manifest['cases']
    if (not isinstance(cases, list) or not cases or len(cases) > 1001
            or any(not isinstance(c, dict) or not isinstance(c.get('candidate_id'), str)
                   or not isinstance(c.get('values'), dict) for c in cases)
            or len({c['candidate_id'] for c in cases}) != len(cases)):
        raise ValueError('Invalid coordinate-study case list.')
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not isinstance(case.get('sha256'), dict):
            raise ValueError('Malformed study case.')
        if index:
            study.check_vector(case['values'], variables)
        elif case['values'] != {}:
            raise ValueError('The first study case must be the neutral baseline.')
        if case.get('status') not in ('FAILED', 'READY_FOR_EXTERNAL'):
            raise ValueError('Invalid coordinate generation status.')
        try:
            candidate = study.candidate(case['values'])
        except (ValueError, ArithmeticError):
            if case['status'] != 'FAILED' or case.get('candidate_hash') is not None or case.get('sha256'):
                raise
        else:
            if project_hash(candidate) != case['candidate_hash']:
                raise ValueError('Candidate parameters do not match their snapshot hash.')
        for name, expected in case.get('sha256', {}).items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts or ':' in name:
                raise ValueError('Invalid coordinate-study payload path.')
            target = directory / relative
            if not target.resolve().is_relative_to(directory.resolve()) or digest(target.read_bytes()) != expected:
                raise ValueError('Coordinate-study output was changed: ' + name)
    if manifest.get('sampling') == 'rbf_external':
        from .coordinate_proposal import validate_proposal_manifest
        validate_proposal_manifest(manifest)
    return study, manifest


def export_study(job):
    """Only numerical section/wall coordinates; no surface, annulus or CAD evaluation."""
    from ..geometry.geometry_3d import generate_impeller, generate_diffuser_3d
    from ..geometry.meridional_segments import generate_meridional
    from ..geometry.row_domain import preview_wall_chunks
    from ..models.blade_rows import row_parameters
    from ..models.geometry_source import GeometrySource
    job = Path(job)
    request = json.loads((job / 'request.json').read_text(encoding='utf-8'))
    if request.get('coordinate_geometry_version') != COORDINATE_GEOMETRY_VERSION:
        raise ValueError('Study geometry version differs. Create a new coordinate study.')
    data = (job / 'snapshot.json').read_bytes()
    if len(data) > 4 * 1024 * 1024 or digest(data) != request['snapshot_hash']:
        raise ValueError('Coordinate-study snapshot mismatch or size limit exceeded.')
    baseline = _decode_v03(json.loads(data), row_snapshot=True)
    study = CoordinateStudy(baseline, request['row_ids'])
    variables = [CoordinateVariable(**v) for v in request['variables']]
    study.validate_variables(variables)
    vectors = request['vectors']
    if not isinstance(vectors, list) or not 1 <= len(vectors) <= 1001 or vectors[0] != {}:
        raise ValueError('A study needs its neutral baseline and at most 1000 candidates.')
    raw_options = dict(request['options'])
    raw_options['columns'] = tuple(raw_options['columns'])
    options = CoordinateCsvOptions(**raw_options)
    options.validate()
    target = Path(request['output'])
    if target.exists():
        raise FileExistsError('Choose a new study directory; existing outputs are protected.')
    proposal_batch = None
    if request['sampling'] == 'rbf_external':
        from .coordinate_proposal import derive_proposals
        proposal_batch, proposal_metadata = derive_proposals(job, request, study, variables)
        vectors = [{}, *proposal_batch['vectors']]
    manifest = {'schema': 'coordinate-study-1', 'run_id': request['run_id'],
                'coordinate_geometry_version': COORDINATE_GEOMETRY_VERSION,
                'baseline_hash': request['snapshot_hash'], 'row_ids': list(study.row_ids),
                'rows': [{'row_id': row.identifier, 'name': row.name, 'kind': row.kind,
                          'directory': f'row_{i + 1:03d}'} for i, row in enumerate(baseline.blade_rows)
                         if row.identifier in study.row_ids],
                'variables': request['variables'], 'options': request['options'],
                'sampling': request['sampling'], 'seed': request['seed'],
                'evaluation_context': request.get('evaluation_context', ''),
                'unit': 'mm', 'rotation_axis': 'Z', 'theta_positive': 'CCW seen from +Z',
                'evaluation': 'EXTERNAL_RESULTS_REQUIRED', 'surface_quality': 'NOT_EVALUATED',
                'cad': 'NOT_EVALUATED', 'cfd': 'NOT_EXECUTED', 'cases': []}
    if proposal_batch is not None:
        manifest['proposal'] = proposal_metadata
    with staged_case(target) as stage:
        if target.exists():
            raise FileExistsError('Study directory was created by another operation.')
        _write_case_files(stage, {'baseline.json': data})
        for ordinal, values in enumerate(vectors):
            print('BLADE_CAD:' + json.dumps({'stage': f'COORDINATE CASE {ordinal + 1}/{len(vectors)}'}), flush=True)
            if ordinal:
                study.check_vector(values, variables)
            case = {'candidate_id': f'case_{ordinal:04d}', 'values': values,
                    'status': 'FAILED', 'sha256': {}, 'rows': []}
            if proposal_batch is not None and ordinal:
                case['prediction'] = proposal_batch['predictions'][ordinal - 1]
            payloads = {}
            try:
                candidate = study.candidate(values)
                case['candidate_hash'] = project_hash(candidate)
                shared_changed = any(v != 0 and study._targets[k][0] is None for k, v in values.items())
                for index, row in enumerate(candidate.blade_rows):
                    if row.identifier not in study.row_ids and not shared_changed:
                        continue
                    params = row_parameters(candidate, row)
                    geometry = generate_impeller(params) if row.kind == 'impeller' else generate_diffuser_3d(params)
                    if row.identifier not in study.row_ids:
                        continue  # Shared-wall edits must also yield valid coordinates for affected unselected rows.
                    source = GeometrySource(row.identifier, row.name, row.kind, 'meridional_3d',
                                            'coordinate_study', case['candidate_hash'])
                    chunks = preview_wall_chunks(candidate, geometry, row.identifier)
                    files = prepare_coordinate_csv(geometry, source, options, 15, wall_chunks=chunks)
                    sections = []
                    for group, profiles in (('main', geometry.sections), ('splitter', geometry.splitter_sections)):
                        for section in profiles or []:
                            sections.append({'group': group, 'span': float(section.span),
                                             'role_order': ['LE', 'PS', 'TE', 'SS'],
                                             'point_counts': {role.upper(): len(getattr(section, 'master_' + role).r)
                                                              for role in ('le', 'ps', 'te', 'ss')}})
                    case['rows'].append({'row_id': row.identifier, 'directory': f'row_{index + 1:03d}',
                                         'sections': sections,
                                         'wall_chunk_point_counts': {wall: [len(chunk.r) for chunk in parts]
                                                                     for wall, parts in chunks.items()}})
                    for name, content in files.items():
                        payloads[f'{case["candidate_id"]}/row_{index + 1:03d}/{name}'] = content
                for wall in ('hub', 'shroud'):
                    curve = generate_meridional(getattr(candidate, wall))
                    stream = io.StringIO(newline='')
                    writer = csv.writer(stream)
                    writer.writerow(['z_mm', 'r_mm'])
                    writer.writerows(zip(curve.z, curve.r))
                    payloads[f'{case["candidate_id"]}/shared_{wall}_rz.csv'] = stream.getvalue().encode('utf-8-sig')
                case['status'] = 'READY_FOR_EXTERNAL'
            except (ValueError, ArithmeticError) as exc:
                case['error'] = str(exc)
                # Even mapping failures retain the attempted values, never a fake score.
                case.setdefault('candidate_hash', None)
                case['rows'] = []
                payloads = {}
                if ordinal == 0:
                    raise ValueError('Baseline coordinate generation failed: ' + str(exc)) from exc
            case['sha256'] = {name: digest(content) for name, content in payloads.items()}
            _write_case_files(stage, payloads)
            manifest['cases'].append(case)
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(['run_id', 'candidate_id', 'candidate_hash', 'evaluation_context', 'status', 'efficiency'])
        for case in manifest['cases']:
            if case['status'] == 'READY_FOR_EXTERNAL':
                writer.writerow([manifest['run_id'], case['candidate_id'], case['candidate_hash'],
                                 manifest['evaluation_context'], 'pending', ''])
        manifest_data = json_bytes(manifest)
        if proposal_batch is not None and len(manifest_data) > 16 * 1024 * 1024:
            raise ValueError('RBF history exceeds the manifest size limit; start a new evaluated Study.')
        _write_case_files(stage, {'manifest.json': manifest_data,
                                 'external_results_template.csv': stream.getvalue().encode('utf-8-sig')})
        if target.exists():
            raise FileExistsError('Study destination appeared during generation; no existing directory replaced.')
    return {'overall': 'PASS', 'phase': 'COORDINATE_STUDY_READY',
            'snapshot_hash': request['snapshot_hash'], 'directory': str(target),
            'run_id': request['run_id'], 'cases': len(manifest['cases'])}


def import_results(path, manifest):
    """Validate the entire CSV before replacing any in-memory results."""
    import math
    fixed = ['run_id', 'candidate_id', 'candidate_hash', 'status']
    known = {case['candidate_id']: case for case in manifest['cases']}
    results = {}
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames
        if not names or len(set(names)) != len(names) or not set(fixed) <= set(names):
            raise ValueError('Results need unique run_id, candidate_id, candidate_hash and status columns.')
        context = manifest.get('evaluation_context', '')
        if context and 'evaluation_context' not in names:
            raise ValueError('Results must include the configured external analysis-condition ID.')
        if 'evaluation_context' in names:
            fixed.append('evaluation_context')
        metrics = [name for name in names if name not in fixed]
        if not metrics or any(not name or name.strip() != name for name in names):
            raise ValueError('Add at least one named numeric evaluation column.')
        for line in reader:
            if None in line or any(value is None for value in line.values()):
                raise ValueError('Malformed result CSV row.')
            identifier = line['candidate_id']
            case = known.get(identifier)
            if (identifier in results or case is None or case['status'] != 'READY_FOR_EXTERNAL'
                    or line['run_id'] != manifest['run_id'] or line['candidate_hash'] != case['candidate_hash']):
                raise ValueError('Duplicate, unknown, changed or wrong-run candidate result.')
            if line.get('evaluation_context', '') != context:
                raise ValueError('External analysis-condition ID does not match this study.')
            status = line['status']
            if status not in ('success', 'failed', 'pending'):
                raise ValueError('Result status must be success, failed or pending.')
            values = {}
            for name in metrics:
                raw = line[name].strip()
                value = float(raw) if raw else None
                if value is not None and (not math.isfinite(value) or status != 'success'):
                    raise ValueError('Use finite success metrics; failed/pending metrics must be empty.')
                values[name] = value
            results[identifier] = {'status': status, 'metrics': values}
    return results


def rank_results(results, objective, maximize=True, constraints=None):
    import math
    if not objective or type(maximize) is not bool:
        raise ValueError('Select an objective and direction.')
    constraints = constraints or {}
    for bounds in constraints.values():
        if (len(bounds) != 2 or any(v is not None and (isinstance(v, bool) or not math.isfinite(v)) for v in bounds)
                or all(v is not None for v in bounds) and bounds[0] > bounds[1]):
            raise ValueError('Invalid metric constraint bounds.')
    def accepted(result):
        metrics = result['metrics']
        value = metrics.get(objective)
        if (result['status'] != 'success' or value is None or isinstance(value, bool)
                or not math.isfinite(value)):
            return False
        return all(metrics.get(name) is not None and not isinstance(metrics[name], bool)
                   and math.isfinite(metrics[name]) and (low is None or metrics[name] >= low)
                   and (high is None or metrics[name] <= high) for name, (low, high) in constraints.items())
    return sorted((key for key, result in results.items() if accepted(result)),
                  key=lambda key: results[key]['metrics'][objective], reverse=maximize)


def main():
    import sys
    job = Path(sys.argv[1])
    try:
        report = export_study(job)
    except Exception as exc:
        report = {'overall': 'FAIL', 'error': {'message': str(exc)}, 'directory': None}
    (job / 'result.json').write_bytes(json_bytes(report))
    sys.exit(0 if report['overall'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
