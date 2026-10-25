"""Read-only correspondence diagnostics for the existing geometry paths.

Preview lines use display indices; CAD uses local master coordinates; trim
blends cylindrical values at common indices. These are different contracts.
No routine here replaces a generated curve or changes an export.
"""
from dataclasses import dataclass
import numpy as np
from .surface_evaluation import SectionSurface, _coordinates


def cad_curve_coordinates(curve):
    """Current CAD client coordinate law (not a physical arclength)."""
    parameter = curve.m_blade_norm
    if parameter is None:parameter = np.linspace(0, 1, len(curve.r))
    parameter = np.asarray(parameter, dtype=float)
    if parameter.ndim != 1 or len(parameter) != len(curve.r) or len(parameter) < 2 or not np.isfinite(parameter).all() or np.any(np.diff(parameter) <= 0):
        raise ValueError("CAD correspondence requires finite strictly increasing curve coordinates.")
    return (parameter-parameter[0])/(parameter[-1]-parameter[0])


def display_master_coordinates(master, display):
    """Map actual resample_curve display vertices onto the CAD master axis.

    For caps without m_norm, interpolate master indices using the same XYZ
    arclength and duplicate filter as resample_curve. Do not use uniform xi.
    This mapping assumes the display curve is the current master's resample;
    reject stale/unrelated display data rather than invent correspondence.
    """
    from .blade_section import resample_curve,curve_sampling
    expected = resample_curve(master, len(display.r))
    # Rake rotates master and display independently after resampling. Repeating
    # XYZ arclength sampling after that rigid rotation differs at roundoff.
    # This scale-bound identity check is not a CAD/geometry acceptance tolerance.
    roundoff = 64*np.finfo(float).eps*max(1., float(np.max(np.abs(master.xyz))))
    keep_extrema=False
    if (expected.xyz.shape==display.xyz.shape and np.isfinite(display.xyz).all()
            and np.max(np.abs(expected.xyz-display.xyz))>roundoff
            and master.meridional_distance is not None):
        for mode in ('le','te'):
            expected=resample_curve(master,len(display.r),keep_extrema=mode)
            keep_extrema=mode
            if np.max(np.abs(expected.xyz-display.xyz))<=roundoff:break
    if expected.xyz.shape != display.xyz.shape or not np.isfinite(display.xyz).all() or np.max(np.abs(expected.xyz-display.xyz)) > roundoff:
        raise ValueError("Display curve is not the current master resample.")
    xi = cad_curve_coordinates(master)
    arc,keep,target=curve_sampling(master,len(display.r),keep_extrema=keep_extrema)
    if arc[-1] == 0:raise ValueError("Collapsed curve has no display correspondence.")
    return np.interp(target, arc[keep], xi[keep])


@dataclass
class CurveProvenance:
    """Source span is per vertex; it is not the derived nominal section span."""
    nominal_span: float
    index: np.ndarray
    cad_xi: np.ndarray
    source_span: np.ndarray
    source_span_kind: str


def curve_provenance(curve, nominal_span):
    nominal_span = float(_coordinates([nominal_span], "Nominal span")[0])
    source = curve.source_span
    kind = "original_geometry" if source is not None else "nominal_section"
    source = np.full(len(curve.r), nominal_span) if source is None else _coordinates(source, "Source span")
    if len(source) != len(curve.r):raise ValueError("Source span must match curve vertices.")
    return CurveProvenance(nominal_span, np.linspace(0, 1, len(curve.r)),
                           cad_curve_coordinates(curve), source.copy(), kind)


def trim_index_surface(sections, role):
    """Actual pre-cut trim interpolation, including the common max-count grid.

    The query coordinate is the common raw-index fraction, not CAD xi.
    Resulting source_span metadata after OD cropping must not be interpreted
    as this coordinate. This function does not reconstruct a cropped TE cap.
    """
    curves = [getattr(section, role) for section in sections]
    count = max(len(curve.r) for curve in curves)
    grid = np.linspace(0, 1, count)
    rows = [np.column_stack([np.interp(grid, np.linspace(0, 1, len(curve.r)), getattr(curve, key))
                             for key in ('r', 'theta_rad', 'z')]) for curve in curves]
    return SectionSurface(rows, [grid]*len(rows), np.array([s.span for s in sections]), cylindrical=True)


def compare_preview_to_spline(sections, role, spline, spans):
    """Sample the actual displayed spanwise polylines against a supplied fit.

    At each line, CAD xi is mapped at row vertices and interpolated linearly
    in nominal span. That explicit convention is not proof of physical point
    correspondence. The supplied spline must describe these same sections
    and role (including its CAD tangent law and density).
    """
    from .wireframe import build_spanwise_wireframe
    if role not in ('le', 'ps', 'te', 'ss'):raise ValueError("Unknown contour role.")
    spans = _coordinates(spans, "Query span")
    lines = [line for line in build_spanwise_wireframe(sections) if line.segment == role.upper()]
    source_spans = np.array([s.span for s in sections])
    mappings = np.array([display_master_coordinates(getattr(s, 'master_'+role), getattr(s, role)) for s in sections])
    # Work line by line; avoid allocating a Cartesian product of paired queries.
    distances = []
    for index, line in enumerate(lines):
        preview = np.column_stack([np.interp(spans, source_spans, line.xyz[:, k]) for k in range(3)])
        xi = np.interp(spans, source_spans, mappings[:, index])
        reference = np.array([spline.evaluate_grid([span], [x])[0, 0] for span, x in zip(spans, xi)])
        distances.extend(np.linalg.norm(preview-reference, axis=1))
    distances = np.asarray(distances)
    return {"max_mm": float(np.max(distances)), "rms_mm": float(np.sqrt(np.mean(distances**2))),
            "span_samples": len(spans), "display_lines": len(lines),
            "max_row_xi_spread": float(np.max(np.ptp(mappings, axis=0))),
            "correspondence": "display_index_to_master_xi; linear_in_nominal_span",
            "scope": "sampled_distance_only; not_Hausdorff_or_quality_gate"}
