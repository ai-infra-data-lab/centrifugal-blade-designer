"""Track derived vertices without changing the existing cylindrical geometry.

An OD intersection or display resample is a blend of source points. Blending
their coordinates alone loses the mixed term on a bilinear source patch;
retain the endpoint coordinates AND their weights instead.
"""
import numpy as np
from ..models.geometry_3d import CurveSourceMap
from .surface_evaluation import SectionSurface, _coordinates, interpolate_span_columns

ROLES = ('camber', 'master_ps', 'master_ss', 'master_le', 'master_te')
SETS = ('sections', 'splitter_sections')


def source_map(span, count, role, source_set='sections', law='source_row_index'):
    return CurveSourceMap(source_set, role, law,
        np.stack((np.full(count, span), np.linspace(0, 1, count)), axis=-1)[:, None, :], np.ones((count, 1)))


def blend_source_map(mapping, left, right, fraction):
    """One blend per result vertex; preserve endpoints, not averaged locations."""
    if mapping is None:return None
    f = np.asarray(fraction)[:, None]
    return CurveSourceMap(mapping.source_set, mapping.role, mapping.law,
        np.concatenate((mapping.coordinates[left], mapping.coordinates[right]), axis=1),
        np.concatenate((mapping.weights[left]*(1-f), mapping.weights[right]*f), axis=1))


def resample_source_map(mapping, arc, keep, target):
    if mapping is None:return None
    indices = np.flatnonzero(keep)
    source = arc[keep]
    if len(source) == 1:
        constant = np.full(len(target), indices[0])
        return blend_source_map(mapping, constant, constant, np.zeros(len(target)))
    right = np.clip(np.searchsorted(source, target, side='right'), 1, len(source)-1)
    left = right-1
    # np.interp (the unchanged geometry path) clamps targets beyond the last
    # retained knot when a tiny final segment was filtered out.
    fraction = np.clip((target-source[left])/(source[right]-source[left]), 0., 1.)
    return blend_source_map(mapping, indices[left], indices[right], fraction)


def evaluate_source_curve(curve, geometry):
    """Reconstruct XYZ using the source geometry's explicit cylindrical law.

    New machined TE caps have no source map and are deliberately rejected.
    This is a provenance diagnostic, not a replacement generator/quality gate.
    """
    mapping = curve.source_map
    if mapping is None:raise ValueError('Curve has no source surface map (including new machined TE caps).')
    if mapping.source_set not in SETS or mapping.role not in ROLES or mapping.law not in ('source_row_index', 'trim_common_index'):
        raise ValueError('Unknown source surface identity or interpolation law.')
    coordinates = np.asarray(mapping.coordinates, dtype=float)
    weights = np.asarray(mapping.weights, dtype=float)
    if coordinates.ndim != 3 or coordinates.shape[0] != len(curve.r) or coordinates.shape[2] != 2 or coordinates.shape[1] < 1 or weights.shape != coordinates.shape[:2]:
        raise ValueError('Source map must match curve vertices and weighted coordinate pairs.')
    _coordinates(coordinates.ravel(), 'Source coordinates')
    if not np.isfinite(weights).all() or np.any(weights < 0) or not np.allclose(weights.sum(axis=1), 1, rtol=0, atol=32*np.finfo(float).eps):
        raise ValueError('Source weights must be finite, nonnegative and sum to one.')
    sections = getattr(geometry, mapping.source_set)
    if not sections:raise ValueError('Source blade set is absent.')
    curves = [getattr(s, mapping.role) for s in sections]
    rows = [np.column_stack((c.r, c.theta_rad, c.z)) for c in curves]
    parameters = [np.linspace(0, 1, len(c.r)) for c in curves]
    if mapping.law == 'trim_common_index':
        grid = np.linspace(0, 1, max(len(c.r) for c in curves))
        rows = [np.column_stack([np.interp(grid, p, row[:, k]) for k in range(3)]) for p, row in zip(parameters, rows)]
        parameters = [grid]*len(rows)
    surface = SectionSurface(rows, parameters, np.array([s.span for s in sections]))
    query = coordinates.reshape(-1, 2)
    values = np.array([np.column_stack([np.interp(query[:, 1], p, row[:, k]) for k in range(3)])
                       for p, row in zip(surface.parameters, surface.rows)])
    values = interpolate_span_columns(values, surface.spans, query[:, 0])
    cylindrical = np.sum(values.reshape(*weights.shape, 3)*weights[:, :, None], axis=1)
    r, theta, z = cylindrical.T
    return np.column_stack((r*np.cos(theta), r*np.sin(theta), z))
