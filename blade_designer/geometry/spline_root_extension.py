"""Polynomial continuation for buried CAD construction, without Qt or CAD APIs."""
from copy import deepcopy
from numbers import Real
import numpy as np
from scipy.interpolate import make_interp_spline
from .surface_evaluation import SplineSurface
from .surface_envelope import _control_net


def extend_spline_root(surface,span_fraction):
    """Continue the first Span polynomial to a common negative parameter.

    Existing interior knots, degree and the mathematical surface on [0,1] are
    retained. Clamped start knots move to -fraction; Greville collocation is an
    exact change of representation in real arithmetic, with float roundoff.
    This surface is only a CAD construction input, not a new blade design.
    """
    if (not isinstance(span_fraction,Real) or isinstance(span_fraction,bool) or
            not np.isfinite(span_fraction) or not 0<span_fraction<=.1):
        raise ValueError('Root Span continuation must be in (0, 0.1].')
    knots,degrees,_=_control_net(surface)
    degree=degrees[0];extended=knots[0].copy();extended[:degree+1]=-float(span_fraction)
    count=len(extended)-degree-1
    coordinates=np.array([np.mean(extended[i+1:i+degree+1]) for i in range(count)])
    if np.any(np.diff(coordinates)<=0):raise ValueError('Root continuation requires distinct Greville coordinates.')
    values=surface.across(coordinates)
    across=make_interp_spline(coordinates,values,k=degree,t=extended,axis=1)
    if not np.isfinite(across.c).all():raise ValueError('Non-finite root continuation coefficients.')
    return SplineSurface(deepcopy(surface.along),across)
