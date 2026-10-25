"""Frozen external-result provenance for coordinate-only RBF batches."""
from dataclasses import asdict
from pathlib import Path
from math import isfinite

from .coordinate_study import digest, json_bytes, project_hash, read_study, import_results
from ..geometry.edge_positioning import COORDINATE_GEOMETRY_VERSION
from ..optimization.surrogate_proposals import propose_candidates


def validate_proposal_manifest(manifest):
    """Reject malformed stored predictions before presenting them in the GUI."""
    proposal = manifest.get('proposal')
    finite = lambda value: type(value) in (int, float) and isfinite(value)
    if (not isinstance(proposal, dict) or proposal.get('model') != 'thin_plate_spline_degree1'
            or proposal.get('feasibility') != 'PREDICTED_ONLY'
            or proposal.get('uncertainty') != 'NOT_ESTIMATED'
            or not isinstance(proposal.get('objective'), str)
            or not isinstance(proposal.get('observations'), list)
            or type(proposal.get('training_count')) is not int
            or not 8 <= proposal['training_count'] <= 250
            or proposal['training_count'] != len(proposal['observations'])
            or not isinstance(proposal.get('seen_vectors'), list) or len(proposal['seen_vectors']) > 2000
            or not isinstance(proposal.get('history_configuration_sha256'), str)
            or type(proposal.get('independent_dimensions')) is not int or proposal['independent_dimensions'] < 1
            or not isinstance(proposal.get('validation_metrics'), dict)):
        raise ValueError('Malformed RBF prediction metadata.')
    if proposal['training_count'] < max(8, 2*proposal['independent_dimensions']+4):
        raise ValueError('RBF metadata has insufficient observations for its dimensions.')
    validation = proposal['validation_metrics'].get(proposal['objective'])
    if (not isinstance(validation, dict) or not finite(validation.get('cv_rmse'))
            or not finite(validation.get('mean_predictor_rmse'))
            or not 0 <= validation['cv_rmse'] < validation['mean_predictor_rmse']):
        raise ValueError('Malformed RBF validation diagnostics.')
    if not 2 <= len(manifest['cases']) <= 51:
        raise ValueError('Invalid RBF case count.')
    if 'prediction' in manifest['cases'][0]:
        raise ValueError('The neutral baseline does not carry a proposal prediction.')
    for case in manifest['cases'][1:]:
        prediction = case.get('prediction')
        if (not isinstance(prediction, dict) or prediction.get('status') != 'PREDICTED_NOT_EVALUATED'
                or prediction.get('strategy') not in ('predicted_objective', 'space_filling')
                or not isinstance(prediction.get('metrics'), dict)
                or proposal['objective'] not in prediction['metrics']
                or any(not finite(value) for value in prediction['metrics'].values())):
            raise ValueError('Malformed unevaluated RBF prediction.')


def freeze_proposal(specification, count):
    if type(count) is not int or not 1 <= count <= 50:
        raise ValueError('Use 1..50 RBF proposals per batch.')
    if not isinstance(specification, dict) or set(specification) != {
            'source_directory', 'manifest_hash', 'results_path', 'results_hash', 'objective', 'maximize', 'constraints'}:
        raise ValueError('Malformed RBF source specification.')
    with Path(specification['results_path']).open('rb') as stream:
        data = stream.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('External results CSV exceeds the 4 MiB limit.')
    if digest(data) != specification['results_hash']:
        raise ValueError('External CSV changed since import; import it again before proposing.')
    request = {key: value for key, value in specification.items() if key not in ('results_path', 'results_hash')}
    request.update(source_directory=str(Path(request['source_directory']).resolve()),
                   results_sha256=digest(data), count=count, schema='rbf-proposal-1')
    return request, data


def derive_proposals(job, request, study, variables):
    spec = request['proposal']
    if not isinstance(spec, dict) or spec.get('schema') != 'rbf-proposal-1':
        raise ValueError('Unsupported RBF proposal specification.')
    _, source = read_study(spec['source_directory'])
    if digest(json_bytes(source)) != spec['manifest_hash']:
        raise ValueError('Source Study changed since it was opened; reopen and import results again.')
    active = lambda values: {v['key']: (v['lower'], v['upper'], v['link']) for v in values if v['enabled']}
    if (source['baseline_hash'] != project_hash(study.baseline)
            or source['coordinate_geometry_version'] != COORDINATE_GEOMETRY_VERSION
            or source['row_ids'] != list(study.row_ids)
            or active(source['variables']) != active([asdict(v) for v in variables])):
        raise ValueError('RBF source baseline, rows or variable settings differ; reopen the original Study.')
    context = source.get('evaluation_context')
    if not context or context != request.get('evaluation_context'):
        raise ValueError('RBF proposals require the same nonempty external analysis-condition ID.')
    results_path = Path(job) / 'external-results.csv'
    if digest(results_path.read_bytes()) != spec['results_sha256']:
        raise ValueError('Frozen external results were changed.')
    results = import_results(results_path, source)
    names = {spec['objective'], *spec['constraints']}
    configuration = digest(json_bytes({'baseline': source['baseline_hash'], 'rows': source['row_ids'],
        'variables': active(source['variables']), 'geometry': COORDINATE_GEOMETRY_VERSION, 'context': context}))
    history = source.get('proposal', {})
    if not isinstance(history, dict):
        raise ValueError('Malformed RBF history.')
    if history and history.get('history_configuration_sha256') != configuration:
        raise ValueError('RBF history configuration differs; start a new evaluated Study.')
    inherited = history.get('observations', [])
    previous = history.get('seen_vectors', [])
    if (not isinstance(inherited, list) or len(inherited) > 250
            or not isinstance(previous, list) or len(previous) > 2000
            or any(not isinstance(o, dict) or not isinstance(o.get('id'), str)
                   or not isinstance(o.get('values'), dict) or not isinstance(o.get('metrics'), dict) for o in inherited)
            or len({o['id'] for o in inherited}) != len(inherited)):
        raise ValueError('Malformed or excessive RBF history observations.')
    for values in [*(o['values'] for o in inherited), *previous]:
        if not isinstance(values, dict):
            raise ValueError('Malformed RBF history vector.')
        if values:study.check_vector(values, variables)
    keys = sorted(active(source['variables']))
    vector_key = lambda values: tuple(values.get(key, 0.) for key in keys)
    if len({vector_key(o['values']) for o in inherited}) != len(inherited):
        raise ValueError('Duplicate inherited observation vectors.')
    observations = {vector_key(o['values']): o for o in inherited
                    if all(o['metrics'].get(name) is not None for name in names)}
    seen = {vector_key(values): values for values in previous}
    incomplete = []; replaced = []; invalidated = []; added = 0; current = set()
    for case in source['cases']:
        key = vector_key(case['values']);seen[key] = case['values']
        identifier = source['run_id'] + '/' + case['candidate_id']
        result = results.get(case['candidate_id'])
        if (case['status'] == 'READY_FOR_EXTERNAL' and result is not None
                and result['status'] == 'success' and all(result['metrics'].get(name) is not None for name in names)):
            if key in current:
                raise ValueError('Duplicate successful source vectors; select one external evaluation explicitly.')
            current.add(key)
            if key in observations:
                replaced.append({'old_id': observations[key]['id'], 'new_id': identifier})
            else:
                added += 1
            observations[key] = {'id': identifier, 'values': case['values'],
                                 'metrics': dict(result['metrics'])}
        else:
            incomplete.append(case['candidate_id'])
            if (case['status'] == 'FAILED' or result is not None and result['status'] == 'failed') and key in observations:
                invalidated.append(observations.pop(key)['id'])
    if history and not added:
        raise ValueError('Evaluate at least one new candidate successfully before the next RBF iteration.')
    if len(seen) > 2000:
        raise ValueError('RBF history exceeds 2000 attempted vectors; start a new Study.')
    observations = list(observations.values());seen = list(seen.values())
    print('BLADE_CAD:{"stage":"RBF MODEL / FOUR-FOLD VALIDATION"}', flush=True)
    batch = propose_candidates(study, variables, observations, seen, spec['count'],
                               request['seed'], spec['objective'], spec['maximize'], spec['constraints'])
    metadata = {'source_run_id': source['run_id'], 'source_manifest_sha256': spec['manifest_hash'],
                'source_results_sha256': spec['results_sha256'], 'objective': spec['objective'],
                'maximize': spec['maximize'], 'constraints': spec['constraints'],
                'external_results': 'NEW_EVALUATIONS_REQUIRED', 'excluded_incomplete_ids': incomplete,
                'history_configuration_sha256': configuration, 'seen_vectors': seen,
                'replaced_observations': replaced, 'invalidated_observations': invalidated,
                'observations': observations, **batch['diagnostics']}
    return batch, metadata
