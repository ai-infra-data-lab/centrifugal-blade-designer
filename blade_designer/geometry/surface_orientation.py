"""Cellwise oriented-normal comparison of corresponding C1 tensor splines.

Real-model Bernstein bounds, not interval-certified floating-point bounds.
Parameter correspondence is a caller contract, not inferred here. No outward
solid orientation, self-intersection test, CAD tolerance or output gate.
"""
from collections import Counter
from math import comb
from numbers import Real
import numpy as np
from .surface_envelope import _control_net, _targets, _insert
from .surface_regularity import _cross_net, _bounds
from .surface_diagnostics import spline_differentials


def _dot_net(first, second):
    """Bernstein product convolution for a scalar dot product."""
    p, q = np.array(first.shape[:2])-1
    r, s = np.array(second.shape[:2])-1
    result = np.zeros((p+r+1, q+s+1))
    for i in range(p+1):
        u = np.array([comb(p,i)*comb(r,k)/comb(p+r,i+k) for k in range(r+1)])
        for j in range(q+1):
            v = np.array([comb(q,j)*comb(s,l)/comb(q+s,j+l) for l in range(s+1)])
            result[i:i+r+1,j:j+s+1] += (second@first[i,j])*u[:,None]*v[None,:]
    return result


def surface_normal_envelope(first, second, *, singular_mm2, refinements=0, max_cells=4096):
    """Bound oriented angle (0..180 degrees) at the same span/role-local xi.

    Same-degree, clamped, nonperiodic splines with C1 original knot structure
    are required. Each common Bezier cell gets a numerical angle upper bound
    only if both Jacobians have positive lower bounds above singular_mm2 and
    all sampled normals exist. Otherwise its bound is None, never zero/PASS.
    A positive dot-product hull bounds the angle by atan2(cross upper, dot
    lower); other regular cells conservatively use 180 degrees. Nine paired
    original-spline samples per cell separately record observed angles.
    """
    if (isinstance(singular_mm2,(bool,np.bool_)) or not isinstance(singular_mm2,Real)
            or not np.isfinite(singular_mm2) or singular_mm2 < 0):
        raise ValueError('singular_mm2 must be finite and nonnegative.')
    if type(refinements) is not int or not 0 <= refinements <= 4:
        raise ValueError('refinements must be an integer from 0 to 4.')
    if type(max_cells) is not int or max_cells < 1:
        raise ValueError('max_cells must be a positive integer.')
    ka, degrees, ca = _control_net(first)
    kb, other_degrees, cb = _control_net(second)
    if degrees != other_degrees:
        raise ValueError('Both surfaces must have the same degrees.')
    for knots in (ka,kb):
        for t,degree in zip(knots,degrees):
            if any(n > degree-1 for knot,n in Counter(t).items() if 0 < knot < 1):
                raise ValueError('Original surfaces must be C1 by knot multiplicity.')
    targets = []
    for a,b,degree in zip(ka,kb,degrees):
        targets.append({k:degree if 0 < k < 1 else degree+1 for k in _targets(a,b,refinements)})
    breaks = [np.array(sorted(t)) for t in targets]
    if (len(breaks[0])-1)*(len(breaks[1])-1) > max_cells:
        raise ValueError('Common Bezier cell count exceeds max_cells.')
    for axis,target in enumerate(targets):
        ka[axis],ca = _insert(ka[axis],ca,degrees[axis],axis,target)
        kb[axis],cb = _insert(kb[axis],cb,degrees[axis],axis,target)
        if not np.array_equal(ka[axis],kb[axis]):
            raise ValueError('Common knots do not match exactly after insertion.')
    p,q = degrees
    cells = []
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            for i,(u0,u1) in enumerate(zip(breaks[0],breaks[0][1:])):
                for j,(v0,v1) in enumerate(zip(breaks[1],breaks[1][1:])):
                    areas,lower = [],[]
                    for coefficients in (ca,cb):
                        net = coefficients[i*p:i*p+p+1,j*q:j*q+q+1]
                        area = _cross_net(p*np.diff(net,axis=0)/(u1-u0),
                                          q*np.diff(net,axis=1)/(v1-v0))
                        lo,hi = _bounds(area)
                        if not np.isfinite([lo,hi]).all():
                            raise ValueError('Normal envelope must be finite.')
                        lower.append(lo)
                        # Independent positive scaling preserves directions and
                        # avoids multiplying dimensionful fourth-order areas.
                        areas.append(area/hi if hi > 0 else area)
                    samples = [spline_differentials(s,[u0,u0+(u1-u0)/2,u1],
                               [v0,v0+(v1-v0)/2,v1],singular_mm2=singular_mm2)
                               for s in (first,second)]
                    valid = ~(samples[0].singular | samples[1].singular)
                    a,b = samples[0].normals[valid],samples[1].normals[valid]
                    angles = np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b),axis=-1),
                                                   np.sum(a*b,axis=-1)))
                    observed = float(angles.max()) if len(angles) else None
                    upper = None
                    if min(lower) > singular_mm2 and valid.all():
                        dot_lower = float(_dot_net(*areas).min())
                        cross_upper = _bounds(_cross_net(*areas))[1]
                        if not np.isfinite([dot_lower,cross_upper]).all():
                            raise ValueError('Normal comparison must be finite.')
                        upper = float(np.degrees(np.arctan2(cross_upper,dot_lower))) if dot_lower > 0 else 180.
                        # Do not hide contradictory floating-point observations.
                        upper = max(upper,observed)
                    cells.append({'span_range':[float(u0),float(u1)],'xi_range':[float(v0),float(v1)],
                                  'first_lower_mm2':lower[0],'second_lower_mm2':lower[1],
                                  'angle_upper_degrees':upper,'sample_max_degrees':observed,
                                  'sample_undefined_pairs':int((~valid).sum())})
    except FloatingPointError as exc:
        raise ValueError('Non-finite arithmetic in normal envelope.') from exc
    unresolved = sum(c['angle_upper_degrees'] is None for c in cells)
    observed = [c['sample_max_degrees'] for c in cells if c['sample_max_degrees'] is not None]
    return {'cells':cells,'cell_count':len(cells),'unresolved_cells':unresolved,
            'angle_upper_degrees':None if unresolved else max(c['angle_upper_degrees'] for c in cells),
            'sample_max_degrees':max(observed) if observed else None,
            'sample_undefined_pairs':sum(c['sample_undefined_pairs'] for c in cells),
            'singular_mm2':float(singular_mm2),'refinements':refinements,'roundoff_certified':False}
