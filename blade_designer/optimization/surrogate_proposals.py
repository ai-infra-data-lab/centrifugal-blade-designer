"""External-observation RBF proposals; no geometry, Qt, files or CFD execution."""
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.spatial.distance import cdist
from scipy.stats import qmc


def propose_candidates(study, variables, observations, seen, count, seed,
                       objective, maximize=True, constraints=None):
    """Fit normalized thin-plate splines, validate out of sample, propose a batch.

    Predictions are estimates, never external results or feasibility guarantees.
    Linked variables form one dimension. All source cases, even failed ones,
    are excluded from the new batch. No input or baseline is modified.
    """
    if (type(count) is not int or not 1 <= count <= 50 or type(seed) is not int
            or not 0 <= seed < 2**32 or type(maximize) is not bool
            or not isinstance(objective, str) or not objective.strip()):
        raise ValueError('Use 1..50 proposals, a 32-bit seed and a named objective/direction.')
    constraints = {} if constraints is None else constraints
    for name, bounds in constraints.items():
        if (not isinstance(name, str) or not name.strip() or len(bounds) != 2
                or any(v is not None and (isinstance(v, bool) or not np.isfinite(v)) for v in bounds)
                or all(v is not None for v in bounds) and bounds[0] > bounds[1]):
            raise ValueError('Invalid prediction constraint bounds.')
    active = study.validate_variables(variables)
    groups = {}
    for v in active:
        groups.setdefault(('link', v.link) if v.link else ('key', v.key), []).append(v)
    axes = list(groups.values())
    if not axes:
        raise ValueError('Enable at least one variable for RBF proposals.')
    lower = np.array([max(v.lower for v in group) for group in axes])
    upper = np.array([min(v.upper for v in group) for group in axes])
    width = upper - lower
    if not np.isfinite(width).all() or np.any(width <= 0):
        raise ValueError('Linked variable bounds need a finite common interval.')

    def coordinates(values):
        # Empty vectors identify the exact neutral baseline, including when
        # zero is outside the search bounds. Nonbaseline vectors stay strict.
        if values:
            study.check_vector(values, variables)
        return (np.array([values.get(group[0].key, 0.) for group in axes]) - lower) / width

    dimension = len(axes)
    minimum = max(8, 2 * dimension + 4)
    if not minimum <= len(observations) <= 250:
        raise ValueError(f'RBF needs {minimum}..250 complete successful observations for {dimension} independent variables; add evaluations or reduce/link variables.')
    names = list(dict.fromkeys([objective, *constraints]))
    identifiers = [o['id'] for o in observations]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate observation IDs.')
    x = np.array([coordinates(o['values']) for o in observations])
    if not np.isfinite(x).all():
        raise ValueError('Non-finite normalized observation coordinates.')
    distances = cdist(x, x)
    np.fill_diagonal(distances, np.inf)
    if np.min(distances) <= 1e-10:
        raise ValueError('Duplicate or indistinguishable observation vectors; no silent averaging.')
    affine = np.column_stack((np.ones(len(x)), x))
    if np.linalg.matrix_rank(affine) != dimension + 1 or np.linalg.cond(affine) > 1e10:
        raise ValueError('Observations do not span the enabled variables reliably.')
    folds = np.array_split(np.random.default_rng(seed).permutation(len(x)), 4)
    pool = qmc.LatinHypercube(d=dimension, seed=seed).random(2048)
    predictions = {}; diagnostics = {}
    for name in names:
        values = [o['metrics'].get(name) for o in observations]
        if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float))
               or not np.isfinite(v) for v in values):
            raise ValueError('Each training row needs finite objective and constraint values.')
        y = np.asarray(values, dtype=float)
        # Normalize the units before variance tests: e.g. W and MW must not
        # change whether an observed objective is considered informative.
        magnitude = float(np.max(np.abs(y))) or 1.
        scaled = y / magnitude
        offset = float(np.mean(scaled)); scale = float(np.std(scaled))
        if scale <= 64 * np.finfo(float).eps:
            if name == objective:
                raise ValueError('The objective has no resolvable observed variation.')
            predictions[name] = np.full(len(pool), float(y[0]))
            diagnostics[name] = {'constant_observed': True, 'cv_rmse': 0., 'mean_predictor_rmse': 0.}
            continue
        normalized = (scaled - offset) / scale
        held_out = np.empty(len(x)); reference = np.empty(len(x))
        for fold in folds:
            training = np.setdiff1d(np.arange(len(x)), fold)
            try:
                model = RBFInterpolator(x[training], normalized[training],
                                        kernel='thin_plate_spline', degree=1, smoothing=1e-6)
                held_out[fold] = model(x[fold])
            except np.linalg.LinAlgError as exc:
                raise ValueError('A validation fold is rank deficient; add independent observations.') from exc
            reference[fold] = np.mean(normalized[training])
        error = float(np.sqrt(np.mean((held_out - normalized)**2)))
        baseline_error = float(np.sqrt(np.mean((reference - normalized)**2)))
        if not np.isfinite(error) or error >= baseline_error:
            raise ValueError(f'{name}: held-out RBF prediction is not better than a training-mean predictor; add observations or reduce variables.')
        model = RBFInterpolator(x, normalized, kernel='thin_plate_spline', degree=1, smoothing=1e-6)
        predictions[name] = (model(pool) * scale + offset) * magnitude
        diagnostics[name] = {'constant_observed': False, 'cv_rmse': error * scale * magnitude,
                             'mean_predictor_rmse': baseline_error * scale * magnitude}
    if any(not np.isfinite(p).all() for p in predictions.values()):
        raise ValueError('Non-finite RBF predictions; no batch generated.')
    eligible = np.ones(len(pool), dtype=bool)
    for name, (low, high) in constraints.items():
        if low is not None: eligible &= predictions[name] >= low
        if high is not None: eligible &= predictions[name] <= high
    previous = np.array([coordinates(values) for values in seen]) if seen else x
    separation = np.min(cdist(pool, previous), axis=1) / np.sqrt(dimension)
    eligible &= separation > 1e-5
    selected = []; strategies = []
    exploit_count = count - count // 4
    for index in range(count):
        candidates = np.flatnonzero(eligible)
        if not len(candidates):
            raise ValueError('Not enough distinct predicted-feasible candidates in the bounded pool.')
        if index < exploit_count:
            score = predictions[objective][candidates]
            chosen = candidates[np.argmax(score) if maximize else np.argmin(score)]
            strategies.append('predicted_objective')
        else:
            chosen = candidates[np.argmax(separation[candidates])]
            strategies.append('space_filling')
        selected.append(int(chosen))
        new_distance = np.linalg.norm(pool - pool[chosen], axis=1) / np.sqrt(dimension)
        separation = np.minimum(separation, new_distance)
        eligible &= new_distance > .02
    vectors = [{v.key: float(value) for group, value in zip(axes, lower + pool[i]*width) for v in group}
               for i in selected]
    for vector in vectors:
        study.check_vector(vector, variables)
    return {'vectors': vectors,
            'predictions': [{'metrics': {name: float(predictions[name][i]) for name in names},
                             'strategy': strategy, 'status': 'PREDICTED_NOT_EVALUATED'}
                            for i, strategy in zip(selected, strategies)],
            'diagnostics': {'model': 'thin_plate_spline_degree1', 'smoothing': 1e-6,
                            'independent_dimensions': dimension, 'training_ids': identifiers,
                            'training_count': len(x), 'minimum_training_count': minimum,
                            'validation': 'seeded_4_fold', 'validation_metrics': diagnostics,
                            'pool_size': len(pool), 'uncertainty': 'NOT_ESTIMATED',
                            'feasibility': 'PREDICTED_ONLY', 'global_optimum': 'NOT_GUARANTEED'}}
