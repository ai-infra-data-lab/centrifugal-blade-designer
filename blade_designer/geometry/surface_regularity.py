"""Piecewise Bernstein bounds for the parametric area vector, not CAD validity.

Bounds hold for the real-arithmetic spline model. Float knot insertion and
arithmetic are not interval-certified. A nonzero Jacobian is only local
regularity; it does not exclude self-intersections or blade interference.
"""
from collections import Counter
from math import comb
from numbers import Real
import numpy as np
from .surface_envelope import _control_net, _targets, _insert
from .surface_diagnostics import spline_differentials


def _cross_net(first, second):
    """Bernstein coefficients of a vector cross product (not polewise cross)."""
    p, q = np.array(first.shape[:2])-1
    r, s = np.array(second.shape[:2])-1
    result = np.zeros((p+r+1, q+s+1, 3))
    for i in range(p+1):
        u = np.array([comb(p,i)*comb(r,k)/comb(p+r,i+k) for k in range(r+1)])
        for j in range(q+1):
            v = np.array([comb(q,j)*comb(s,l)/comb(q+s,j+l) for l in range(s+1)])
            result[i:i+r+1,j:j+s+1] += np.cross(first[i,j],second)*u[:,None,None]*v[None,:,None]
    return result


def _center(net):
    p, q = np.array(net.shape[:2])-1
    u = np.array([comb(p,i)*.5**p for i in range(p+1)])
    v = np.array([comb(q,j)*.5**q for j in range(q+1)])
    return np.einsum('i,j,ijc->c',u,v,net)


def _bounds(net):
    low, high = net.min(axis=(0,1)), net.max(axis=(0,1))
    lower = float(np.linalg.norm(np.maximum(np.maximum(low,-high),0)))
    upper = float(np.max(np.linalg.norm(net,axis=-1)))
    center = _center(net)
    norm = np.linalg.norm(center)
    if norm > 0:
        # A separating projection can improve the axis-aligned box bound.
        lower = max(lower,float(np.min(net@(center/norm))))
    return lower, upper


def surface_jacobian_envelope(surface, *, singular_mm2, refinements=0, max_cells=4096):
    """Bound |dS/dspan cross dS/dxi| on each complete Bezier cell.

    Original surfaces must be C1 by knot multiplicity; no smoothing at seams.
    Unresolved hulls are not singularity proofs. Nine original-spline samples
    per cell independently record observed values at/below the caller threshold.
    No PASS/FAIL, outward normal, rounding certificate or collision test.
    """
    if (isinstance(singular_mm2,(bool,np.bool_)) or not isinstance(singular_mm2,Real)
            or not np.isfinite(singular_mm2) or singular_mm2 < 0):
        raise ValueError('singular_mm2 must be finite and nonnegative.')
    if type(refinements) is not int or not 0 <= refinements <= 4:
        raise ValueError('refinements must be an integer from 0 to 4.')
    if type(max_cells) is not int or max_cells < 1:
        raise ValueError('max_cells must be a positive integer.')
    knots, degrees, coefficients = _control_net(surface)
    # Translation does not change derivatives. Remove the large absolute
    # origin before repeated knot insertion and small-cell differencing.
    coefficients=coefficients-coefficients[0,0]
    targets = []
    for t, degree in zip(knots,degrees):
        if any(count > degree-1 for knot,count in Counter(t).items() if 0 < knot < 1):
            raise ValueError('Original surface must be C1 by knot multiplicity.')
        target = _targets(t,t,refinements)
        targets.append({knot:degree if 0 < knot < 1 else degree+1 for knot in target})
    breaks = [np.array(sorted(t)) for t in targets]
    cell_counts = [len(t)-1 for t in breaks]
    if cell_counts[0]*cell_counts[1] > max_cells:
        raise ValueError('Bezier cell count exceeds max_cells.')
    for axis,target in enumerate(targets):
        knots[axis],coefficients = _insert(knots[axis],coefficients,degrees[axis],axis,target)
    p, q = degrees
    cells = []
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            for i,(u0,u1) in enumerate(zip(breaks[0],breaks[0][1:])):
                for j,(v0,v1) in enumerate(zip(breaks[1],breaks[1][1:])):
                    net = coefficients[i*p:i*p+p+1,j*q:j*q+q+1]
                    ds = p*np.diff(net,axis=0)/(u1-u0)
                    dx = q*np.diff(net,axis=1)/(v1-v0)
                    area = _cross_net(ds,dx)
                    lower,upper = _bounds(area)
                    sample = spline_differentials(surface,[u0,u0+(u1-u0)/2,u1],
                                                   [v0,v0+(v1-v0)/2,v1],singular_mm2=singular_mm2)
                    sample_min = float(sample.jacobian_mm2.min())
                    if not np.isfinite([lower,upper,sample_min]).all():
                        raise ValueError('Jacobian envelope must be finite.')
                    observed = bool(sample.singular.any())
                    # Keep contradictory numerical evidence unresolved.
                    regular = lower > singular_mm2 and not observed
                    cells.append({'span_range':[float(u0),float(u1)],'xi_range':[float(v0),float(v1)],
                                  'lower_mm2':lower,'upper_mm2':upper,'sample_min_mm2':sample_min,
                                  'numeric_regular':bool(regular),'sampled_at_or_below_threshold':observed})
    except FloatingPointError as exc:
        raise ValueError('Non-finite arithmetic in Jacobian envelope.') from exc
    return {'cells':cells,'cell_count':len(cells),
            'numeric_regular_cells':sum(c['numeric_regular'] for c in cells),
            'unresolved_cells':sum(not c['numeric_regular'] for c in cells),
            'sampled_at_or_below_threshold_cells':sum(c['sampled_at_or_below_threshold'] for c in cells),
            'min_lower_mm2':min(c['lower_mm2'] for c in cells),
            'max_upper_mm2':max(c['upper_mm2'] for c in cells),
            'sample_min_mm2':min(c['sample_min_mm2'] for c in cells),
            'singular_mm2':float(singular_mm2),'refinements':refinements,'roundoff_certified':False}
