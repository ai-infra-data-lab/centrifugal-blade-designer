import numpy as np
from ..models.geometry import BladeSegment, FloatArray
from .resample import arc_length, segment_spline


def calculate_curvature(segment: BladeSegment) -> FloatArray:
    s, spline = segment_spline(segment)
    if spline is None:
        raise ValueError("Cannot calculate curvature for a collapsed surface.")
    first, second = spline(arc_length(segment), 1), spline(arc_length(segment), 2)
    speed = np.hypot(first[:, 0], first[:, 1])
    if np.any(speed < 1e-12):
        raise ValueError("Surface cusp: spline tangent vanishes.")
    return (first[:, 0]*second[:, 1] - first[:, 1]*second[:, 0]) / speed**3
