"""Sampled differential diagnostics, not a surface validity or collision gate.

Coordinates are dimensionless (span, role-local xi); XYZ is in millimetres.
Normals use dS/dspan cross dS/dxi, not the CAD solid's outward orientation.
"""
from dataclasses import dataclass
from numbers import Real
import numpy as np
from scipy.interpolate import BSpline
from .surface_evaluation import SplineSurface, _coordinates


@dataclass
class SurfaceDifferentials:
    xyz: np.ndarray
    d_span: np.ndarray
    d_xi: np.ndarray
    jacobian_mm2: np.ndarray
    normals: np.ndarray
    singular: np.ndarray


def spline_differentials(surface, spans, coordinates, *, singular_mm2):
    """Analytic spline derivatives on the requested tensor grid.

    The caller supplies an explicit nonnegative area-density threshold.
    Normals at singular samples are NaN, never zero or a substituted normal.
    No assumptions are made about unvisited locations or outward orientation.
    """
    if not isinstance(surface, SplineSurface):
        raise ValueError('Analytic diagnostics require a SplineSurface.')
    if (isinstance(singular_mm2, (bool, np.bool_)) or not isinstance(singular_mm2, Real)
            or not np.isfinite(singular_mm2) or singular_mm2 < 0):
        raise ValueError('singular_mm2 must be finite and nonnegative.')
    spans = _coordinates(spans, 'Query span')
    coordinates = _coordinates(coordinates, 'Query segment')
    coefficients = np.moveaxis(surface.across(spans), 1, 0)
    span_coefficients = np.moveaxis(surface.across.derivative()(spans), 1, 0)
    along = BSpline(surface.along.t, coefficients, surface.along.k, axis=1)
    xyz = along(coordinates)
    d_xi = along.derivative()(coordinates)
    d_span = BSpline(surface.along.t, span_coefficients, surface.along.k, axis=1)(coordinates)
    if not all(np.isfinite(a).all() for a in (xyz, d_span, d_xi)):
        raise ValueError('Surface positions and derivatives must be finite.')
    cross = np.cross(d_span, d_xi)
    jacobian = np.linalg.norm(cross, axis=-1)
    if not np.isfinite(jacobian).all():
        raise ValueError('Surface Jacobian must be finite.')
    singular = jacobian <= singular_mm2
    normals = np.full_like(cross, np.nan)
    np.divide(cross, jacobian[..., None], out=normals, where=~singular[..., None])
    return SurfaceDifferentials(xyz, d_span, d_xi, jacobian, normals, singular)


def compare_spline_differentials(first, second, spans, coordinates, *, singular_mm2):
    """Corresponding-sample distance and oriented normal angle in degrees.

    Correspondence must be established by the caller. Invalid normal pairs
    are counted explicitly; all-invalid angles return None, not a PASS/zero.
    """
    a = spline_differentials(first, spans, coordinates, singular_mm2=singular_mm2)
    b = spline_differentials(second, spans, coordinates, singular_mm2=singular_mm2)
    distances = np.linalg.norm(a.xyz-b.xyz, axis=-1)
    valid = ~(a.singular | b.singular)
    # atan2 is stable near both zero and 180 degrees; keep orientation signs.
    dot = np.sum(a.normals[valid]*b.normals[valid], axis=-1)
    cross = np.linalg.norm(np.cross(a.normals[valid], b.normals[valid]), axis=-1)
    angles = np.degrees(np.arctan2(cross, dot))
    return {'max_mm': float(distances.max()),
            'rms_mm': float(np.sqrt(np.mean(distances**2))),
            'max_normal_degrees': float(angles.max()) if len(angles) else None,
            'valid_normal_pairs': int(valid.sum()),
            'first_singular_samples': int(a.singular.sum()),
            'second_singular_samples': int(b.singular.sum()),
            'first_min_jacobian_mm2': float(a.jacobian_mm2.min()),
            'second_min_jacobian_mm2': float(b.jacobian_mm2.min()),
            'span_samples': len(spans), 'segment_samples': len(coordinates)}
