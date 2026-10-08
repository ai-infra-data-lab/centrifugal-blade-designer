import numpy as np
from scipy.interpolate import CubicSpline
from ..models.geometry import BladeSegment, BladeSurfaceGeometry, FloatArray
from ..models.parameters import OutputPointParameters


def arc_length(segment: BladeSegment) -> FloatArray:
    return np.r_[0., np.cumsum(np.hypot(np.diff(segment.x), np.diff(segment.y)))]


def segment_spline(segment: BladeSegment) -> tuple[FloatArray, CubicSpline | None]:
    s = arc_length(segment)
    keep = np.r_[True, np.diff(s) > 0]
    s = s[keep]
    if len(s) < 2:
        return s, None
    return s, CubicSpline(s, segment.xy[keep], axis=0)


def resample_segment(segment: BladeSegment, n_points: int) -> BladeSegment:
    if n_points < 2:
        raise ValueError("At least two segment points are required.")
    s = arc_length(segment)
    target = np.linspace(0., s[-1], n_points)
    # Dense-master piecewise linear arc interpolation preserves endpoints and equal arc spacing.
    keep = np.r_[True, np.diff(s) > 0]
    x = np.interp(target, s[keep], segment.x[keep])
    y = np.interp(target, s[keep], segment.y[keep])
    m = None if segment.m_norm is None else np.interp(target, s[keep], segment.m_norm[keep])
    return BladeSegment(x, y, m)


def resample_surfaces(master: BladeSurfaceGeometry, counts: OutputPointParameters) -> BladeSurfaceGeometry:
    return BladeSurfaceGeometry(**{
        name: resample_segment(getattr(master, name), getattr(counts, name + "_points"))
        for name in ("ps", "ss", "le", "te")
    })


def closed_contour(surfaces: BladeSurfaceGeometry, repeat_first: bool = False) -> tuple[FloatArray, list[str]]:
    arrays = [surfaces.le.xy[:-1], surfaces.ps.xy[:-1], surfaces.te.xy[:-1], surfaces.ss.xy[::-1][:-1]]
    labels = [name for name, points in zip(("LE", "PS", "TE", "SS"), arrays) for _ in points]
    xy = np.concatenate(arrays)
    # Zero-thickness edges collapse; also remove these duplicate joins.
    keep = np.r_[True, np.any(np.diff(xy, axis=0) != 0, axis=1)]
    xy, labels = xy[keep], [label for label, take in zip(labels, keep) if take]
    if len(xy) > 1 and np.array_equal(xy[-1], xy[0]):
        xy, labels = xy[:-1], labels[:-1]
    if repeat_first:
        xy, labels = np.vstack((xy, xy[0])), labels + [labels[0]]
    return xy, labels
