"""Replaceable span mapping; wall curves are paired at equal flow-path fraction."""
import numpy as np
from .meridional_segments import sample_meridional


def interpolate_span_position(hub,shroud,span,flow_fraction,shroud_fraction=None):
    shroud_fraction=flow_fraction if shroud_fraction is None else shroud_fraction
    if not np.isfinite(span) or not 0<=span<=1:
        raise ValueError("Span must be finite and between 0 and 1.")
    return ((1-span)*sample_meridional(hub,np.asarray(flow_fraction)*hub.length)
            +span*sample_meridional(shroud,np.asarray(shroud_fraction)*shroud.length))
