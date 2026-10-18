"""Control-net distance envelopes for corresponding tensor spline surfaces.

The convex-hull bound is global in exact arithmetic. Float knot insertion is
not interval arithmetic: this is numerical evidence, not a certified tolerance
or a CAD/STEP validity gate. Both parameter directions must already correspond.
"""
from collections import Counter
import numpy as np
from scipy.interpolate import BSpline
from .surface_evaluation import SplineSurface


def _control_net(surface):
    if not isinstance(surface, SplineSurface):
        raise ValueError('Envelope requires a SplineSurface.')
    knots = []
    degrees = []
    for spline in (surface.across, surface.along):
        t = np.asarray(spline.t, dtype=float)
        k = spline.k
        if (spline.axis != 1 or spline.extrapolate == 'periodic'
                or k not in (1, 2, 3) or not np.isfinite(t).all()
                or np.any(np.diff(t) < 0) or len(t) < 2*(k+1)
                or not np.all(t[:k+1] == 0) or not np.all(t[-k-1:] == 1)
                or np.any((t < 0) | (t > 1))
                or max(Counter(t).values()) > k+1):
            raise ValueError('Requires clamped degree 1..3 tensor splines on [0, 1].')
        knots.append(t.copy())
        degrees.append(k)
    shape = tuple(len(t)-k-1 for t, k in zip(knots, degrees))+(3,)
    coefficients = np.asarray(surface.across.c)
    if (coefficients.shape != shape or not np.isrealobj(coefficients)
            or not np.isfinite(coefficients).all()):
        raise ValueError('Finite real XYZ tensor coefficients must match both knot vectors.')
    return knots, degrees, coefficients.astype(float, copy=True)


def _targets(first, second, refinements):
    multiplicities = Counter(first) | Counter(second)
    for _ in range(refinements):
        points = sorted(multiplicities)
        for a, b in zip(points, points[1:]):
            midpoint = a+(b-a)/2
            if not a < midpoint < b:
                raise ValueError('Knot interval cannot be refined at floating-point precision.')
            multiplicities[midpoint] = 1
    return multiplicities


def _insert(knots, coefficients, degree, axis, target):
    spline = BSpline(knots, np.moveaxis(coefficients, axis, 0), degree, axis=0)
    existing = Counter(knots)
    for knot, multiplicity in sorted(target.items()):
        missing = multiplicity-existing[knot]
        if missing:
            spline = spline.insert_knot(float(knot), missing)
    net = np.moveaxis(spline.c, 0, axis)
    if not np.isfinite(net).all():
        raise ValueError('Knot insertion produced non-finite coefficients.')
    return spline.t, net


def surface_distance_envelope(first, second, *, refinements=0, max_control_points=250000):
    """Return an exact-arithmetic convex-hull upper estimate and sampled lower.

    No degree elevation, knot merging, physical matching, automatic repair or
    PASS/FAIL. Refinements insert all interval midpoints, never refit a surface.
    The coefficient cap rejects an oversized request before refinement allocates
    the common tensor nets. Float rounding is explicitly not certified.
    """
    if type(refinements) is not int or not 0 <= refinements <= 4:
        raise ValueError('refinements must be an integer from 0 to 4.')
    if type(max_control_points) is not int or max_control_points < 1:
        raise ValueError('max_control_points must be a positive integer.')
    ka, degrees, ca = _control_net(first)
    kb, other_degrees, cb = _control_net(second)
    if degrees != other_degrees:
        raise ValueError('Both surfaces must have the same degrees; degree elevation is unsupported.')
    targets = [_targets(a, b, refinements) for a, b in zip(ka, kb)]
    counts = [sum(target.values())-k-1 for target, k in zip(targets, degrees)]
    if counts[0]*counts[1] > max_control_points:
        raise ValueError('Common surface control net exceeds max_control_points.')
    for axis, target in enumerate(targets):
        ka[axis], ca = _insert(ka[axis], ca, degrees[axis], axis, target)
        kb[axis], cb = _insert(kb[axis], cb, degrees[axis], axis, target)
        if not np.array_equal(ka[axis], kb[axis]):
            raise ValueError('Common knots do not match exactly after insertion.')
    upper = float(np.max(np.linalg.norm(ca-cb, axis=-1)))
    # Knot locations and cell midpoints provide a lower estimate independent of
    # the control-hull upper. Evaluate one span row at a time to bound memory.
    queries = []
    for knots in ka:
        unique = np.unique(knots)
        queries.append(np.sort(np.concatenate((unique, unique[:-1]+np.diff(unique)/2))))
    lower = 0.
    for span in queries[0]:
        difference = first.evaluate_grid([span], queries[1])-second.evaluate_grid([span], queries[1])
        lower = max(lower, float(np.max(np.linalg.norm(difference, axis=-1))))
    if not np.isfinite([lower, upper]).all():
        raise ValueError('Distance envelope must be finite.')
    return {'sample_lower_mm': lower, 'control_upper_mm': upper,
            'numerical_bracket_gap_mm': upper-lower,
            'span_controls': counts[0], 'xi_controls': counts[1],
            'span_samples': len(queries[0]), 'xi_samples': len(queries[1]),
            'refinements': refinements, 'roundoff_certified': False}
