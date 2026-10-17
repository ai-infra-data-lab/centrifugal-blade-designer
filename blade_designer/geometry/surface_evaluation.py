"""Explicit section-surface contracts, independent of Qt, CAD and file formats.

The existing Cartesian CAD spline and cylindrical trim interpolation are
different surfaces. Sharing evaluation code does not make them equivalent.
Coordinates are segment-local in [0, 1], not closed-contour point indices.
"""
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import BSpline, make_interp_spline


def _coordinates(values, label):
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or not len(result) or not np.isfinite(result).all() or np.any((result < 0) | (result > 1)):
        raise ValueError(f"{label} must be finite coordinates within [0, 1].")
    return result


def validate_surface_rows(rows, parameters=None, spans=None):
    rows = [np.asarray(row, dtype=float) for row in rows]
    if len(rows) < 2 or any(row.ndim != 2 or row.shape[1] != 3 or len(row) < 2 or not np.isfinite(row).all() for row in rows):
        raise ValueError("Surface requires finite Nx3 Hub/Tip rows.")
    spans = _coordinates(np.linspace(0, 1, len(rows)) if spans is None else spans, "Span")
    if len(spans) != len(rows) or spans[0] != 0 or spans[-1] != 1 or np.any(np.diff(spans) <= 0):
        raise ValueError("Surface spans must increase strictly from Hub 0 to Tip 1.")
    parameters = [np.linspace(0, 1, len(row)) for row in rows] if parameters is None else parameters
    if len(parameters) != len(rows):raise ValueError("Surface parameter row count mismatch.")
    coordinates = []
    for row, source in zip(rows, parameters):
        source = _coordinates(source, "Segment")
        if len(source) != len(row) or source[0] != 0 or source[-1] != 1 or np.any(np.diff(source) <= 0):
            raise ValueError("Segment coordinates must increase strictly from 0 to 1 and match the row.")
        coordinates.append(source)
    return rows, coordinates, spans


def interpolate_span_columns(values, spans, target):
    """Existing trim blend, also applicable to Cartesian XYZ columns.

    One target span per streamwise column. No angle wrapping or projection.
    """
    values = np.asarray(values)
    spans = _coordinates(spans, "Span")
    target = _coordinates(target, "Target span")
    if len(spans) < 2 or spans[0] != 0 or spans[-1] != 1 or np.any(np.diff(spans) <= 0):
        raise ValueError("Surface spans must increase strictly from Hub 0 to Tip 1.")
    if values.ndim < 2 or values.shape[:2] != (len(spans), len(target)) or not np.isfinite(values).all():
        raise ValueError("Span values must match source spans and target columns.")
    index = np.clip(np.searchsorted(spans, target, side='right')-1, 0, len(spans)-2)
    f = (target-spans[index])/(spans[index+1]-spans[index])
    if values.ndim > 2:f = f.reshape((-1,)+(1,)*(values.ndim-2))
    col = np.arange(len(target))
    return values[index, col]*(1-f)+values[index+1, col]*f


@dataclass
class SectionSurface:
    """Piecewise row interpolation: Cartesian chords or cylindrical r/theta/z.

    Cylindrical theta must already be unwrapped; no automatic correction is
    made. Coordinates must be supplied for each role and sampling convention.
    """
    rows: list
    parameters: list
    spans: np.ndarray
    cylindrical: bool = False

    def __post_init__(self):
        rows, parameters, spans = validate_surface_rows(self.rows, self.parameters, self.spans)
        self.rows = [row.copy() for row in rows]
        self.parameters = [source.copy() for source in parameters]
        self.spans = spans.copy()
        if self.cylindrical and any(np.any(row[:, 0] <= 0) for row in self.rows):
            raise ValueError("Cylindrical surface radii must be positive.")

    def evaluate_grid(self, spans, coordinates):
        spans = _coordinates(spans, "Query span")
        coordinates = _coordinates(coordinates, "Query segment")
        values = np.array([np.column_stack([np.interp(coordinates, p, row[:, k]) for k in range(3)])
                           for row, p in zip(self.rows, self.parameters)])
        result = np.array([interpolate_span_columns(values, self.spans, np.full(len(coordinates), span)) for span in spans])
        if self.cylindrical:
            r, theta, z = np.moveaxis(result, -1, 0)
            result = np.stack((r*np.cos(theta), r*np.sin(theta), z), axis=-1)
        return result


@dataclass
class SplineSurface:
    """Numerical representation of the existing Cartesian CAD tensor spline."""
    along: BSpline
    across: BSpline

    def evaluate_grid(self, spans, coordinates):
        spans = _coordinates(spans, "Query span")
        coordinates = _coordinates(coordinates, "Query segment")
        # SciPy restores the queried axis at across.axis (1), whereas its
        # stored CAD coefficients put span poles first.
        coefficients = np.moveaxis(self.across(spans), 1, 0)
        return BSpline(self.along.t, coefficients, self.along.k, axis=1)(coordinates)


def fit_surface_spline(rows, count, parameters=None, spans=None, tangents=None):
    """Same knot construction, sampling and coefficient order as legacy CAD."""
    rows, parameters, spans = validate_surface_rows(rows, parameters, spans)
    if isinstance(count, bool) or not isinstance(count, (int, np.integer)) or count < 2:
        raise ValueError("Surface grid count must be an integer >= 2.")
    xi = np.linspace(0, 1, count)
    samples = np.array([np.column_stack([np.interp(xi, source, row[:, k]) for k in range(3)]) for row, source in zip(rows, parameters)])
    if tangents is not None:
        tangents = np.asarray(tangents, dtype=float)
        if tangents.shape != (2, len(rows), 3) or not np.isfinite(tangents).all():
            raise ValueError("Surface end tangents must have shape (2, rows, 3).")
    along = make_interp_spline(xi, samples, k=min(3, count-1), axis=1,
                              bc_type=None if tangents is None else ([(1, tangents[0])], [(1, tangents[1])]))
    across = make_interp_spline(spans, along.c, k=min(3, len(rows)-1), axis=1)
    return SplineSurface(along, across)


def compare_surfaces(first, second, spans, coordinates):
    """Corresponding-grid distance only; neither Hausdorff nor collision proof."""
    delta = first.evaluate_grid(spans, coordinates)-second.evaluate_grid(spans, coordinates)
    distances = np.linalg.norm(delta, axis=-1)
    return {"max_mm": float(np.max(distances)), "rms_mm": float(np.sqrt(np.mean(distances**2))),
            "span_samples": len(spans), "segment_samples": len(coordinates)}
