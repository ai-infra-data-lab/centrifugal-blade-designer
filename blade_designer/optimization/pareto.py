"""Direction-aware nondominated fronts and crowding; no Qt, IO or geometry."""
import numpy as np


def objective_definitions(objectives):
    """Two named objectives; never turn them into a weighted sum."""
    if (not isinstance(objectives, (list, tuple)) or len(objectives) != 2
            or any(not isinstance(o, dict) or set(o) != {'name', 'maximize'}
                   or not isinstance(o['name'], str) or not o['name'].strip()
                   or o['name'] != o['name'].strip() or type(o['maximize']) is not bool
                   for o in objectives)
            or len({o['name'] for o in objectives}) != len(objectives)):
        raise ValueError('Use two distinct objective names and explicit maximize/minimize directions.')
    return [dict(o) for o in objectives]


def pareto_order(values, maximize):
    """Return indices and 1-based fronts; ties use stable input order.

    Crowding uses objective ranges within each front. Constant axes contribute
    nothing; equal vectors remain nondominated ties. Sorting is bounded O(N²).
    """
    data = np.asarray(values, dtype=float)
    directions = list(maximize)
    if (data.ndim != 2 or data.shape[1] != len(directions)
            or len(directions) != 2 or len(data) > 2048
            or any(type(v) is not bool for v in directions) or not np.isfinite(data).all()):
        raise ValueError('Use a finite matrix of at most 2048 points and two objective directions.')
    # Unit normalization avoids overflow in crowding ranges without changing
    # the strict dominance comparison. Positive unit scaling preserves order.
    magnitude = np.max(np.abs(data), axis=0) if len(data) else np.ones(len(directions))
    scaled = data / np.where(magnitude == 0, 1., magnitude)
    signs = np.array([-1. if v else 1. for v in directions])
    loss = data * signs
    crowding_loss = scaled * signs
    dominates = np.zeros((len(data), len(data)), dtype=bool)
    for i, row in enumerate(loss):
        dominates[i] = np.all(row <= loss, axis=1) & np.any(row < loss, axis=1)
    counts = dominates.sum(axis=0)
    ranks = np.zeros(len(data), dtype=int)
    order = []; rank = 1
    while np.any(ranks == 0):
        front = np.flatnonzero((counts == 0) & (ranks == 0))
        if not len(front):
            raise ValueError('Invalid dominance graph.')
        crowding = np.zeros(len(front))
        for axis in range(len(directions)):
            axis_order = np.argsort(crowding_loss[front, axis], kind='stable')
            sorted_values = crowding_loss[front[axis_order], axis]
            width = sorted_values[-1] - sorted_values[0]
            if width == 0:
                continue
            crowding[axis_order[[0, -1]]] = np.inf
            if len(front) > 2:
                crowding[axis_order[1:-1]] += (sorted_values[2:] - sorted_values[:-2]) / width
        order.extend(front[np.argsort(-crowding, kind='stable')].tolist())
        ranks[front] = rank
        counts -= dominates[front].sum(axis=0)
        rank += 1
    return order, ranks.tolist()
