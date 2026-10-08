"""Adjustable diagnostic thresholds; geometry warnings are not performance predictions."""
import numpy as np
from scipy.spatial import cKDTree
from ..models.geometry import BladeSurfaceGeometry, CurvatureGeometry, FloatArray
from ..models.parameters import EdgeParameters, EdgeType
from ..models.validation import ValidationIssue, ValidationLevel
from .resample import closed_contour

TANGENT_WARNING_DEG = 5.
MAX_CURVATURE = 1.0  # 1/mm
RADIUS_THICKNESS_RATIO = 1.0
CUSP_PROJECTION_THRESHOLD = 0.0


def has_self_intersection(xy: FloatArray) -> bool:
    if len(xy) < 4:
        return False
    starts, ends = xy, np.roll(xy, -1, axis=0)
    half = np.linalg.norm(ends-starts, axis=1)/2
    pairs = cKDTree((starts+ends)/2).query_pairs(2*float(half.max()), output_type="ndarray")
    if not len(pairs):
        return False
    i, j = pairs.T
    keep = ((j-i) != 1) & ~((i == 0) & (j == len(xy)-1))
    i, j = i[keep], j[keep]
    if not len(i):
        return False
    a, b, c, d = starts[i], ends[i], starts[j], ends[j]
    def cross(u: FloatArray, v: FloatArray) -> FloatArray:
        return u[:, 0]*v[:, 1] - u[:, 1]*v[:, 0]
    ab, cd = b-a, d-c
    o1, o2, o3, o4 = cross(ab, c-a), cross(ab, d-a), cross(cd, a-c), cross(cd, b-c)
    scale = max(float(np.ptp(xy, axis=0).max()), 1.)
    tol = 1e-12*scale**2
    proper = (((o1 > tol) & (o2 < -tol)) | ((o1 < -tol) & (o2 > tol))) & (((o3 > tol) & (o4 < -tol)) | ((o3 < -tol) & (o4 > tol)))
    bbox = np.all(np.maximum(np.minimum(a,b), np.minimum(c,d)) <= np.minimum(np.maximum(a,b), np.maximum(c,d)) + 1e-12*scale, axis=1)
    touching = bbox & (np.minimum(o1,o2) <= tol) & (np.maximum(o1,o2) >= -tol) & (np.minimum(o3,o4) <= tol) & (np.maximum(o3,o4) >= -tol)
    return bool(np.any(proper | touching))


def check_geometry(surfaces: BladeSurfaceGeometry, curvature: CurvatureGeometry,
                   thickness: FloatArray, direction: FloatArray, edges: EdgeParameters) -> list[ValidationIssue]:
    issues = []
    def warn(field: str, message: str) -> None:
        issues.append(ValidationIssue(ValidationLevel.WARNING, field, message))
    for name in ("ps", "ss", "le", "te"):
        if not np.all(np.isfinite(getattr(surfaces, name).xy)):
            raise ValueError(f"{name.upper()} contains NaN or infinite coordinates.")
    for label, a, b in (
        ("LE-PS", surfaces.le.xy[-1], surfaces.ps.xy[0]),
        ("LE-SS", surfaces.le.xy[0], surfaces.ss.xy[0]),
        ("TE-PS", surfaces.te.xy[0], surfaces.ps.xy[-1]),
        ("TE-SS", surfaces.te.xy[-1], surfaces.ss.xy[-1])):
        if not np.allclose(a, b, rtol=0, atol=1e-9):
            raise ValueError(f"Position discontinuity at {label}.")
    for leading, kind, edge in ((True, edges.le_type, surfaces.le), (False, edges.te_type, surfaces.te)):
        if kind == EdgeType.CUTOFF:
            continue
        e = edge.xy
        edge_vectors = (e[-1]-e[-2], e[1]-e[0]) if leading else (e[1]-e[0], e[-1]-e[-2])
        for side, vector, sign in zip((surfaces.ps, surfaces.ss), edge_vectors, (1., -1.)):
            vector_s = side.xy[1]-side.xy[0] if leading else side.xy[-1]-side.xy[-2]
            norm = np.linalg.norm(vector)*np.linalg.norm(vector_s)
            if norm > 0:
                angle = np.rad2deg(np.arccos(np.clip(sign*(vector @ vector_s)/norm, -1., 1.)))
                if angle > TANGENT_WARNING_DEG:
                    warn("edges", f"{'LE' if leading else 'TE'} rounded-edge tangent mismatch: {angle:.2f} deg.")
    for name, k in (("ps", curvature.ps_curvature), ("ss", curvature.ss_curvature)):
        if np.max(np.abs(k)) > MAX_CURVATURE:
            warn(name, f"{name.upper()}: very large local curvature.")
        if np.any(np.abs(k) * thickness >= 1/RADIUS_THICKNESS_RATIO):
            warn(name, f"{name.upper()}: curvature radius is comparable to local thickness.")
        xy = getattr(surfaces, name).xy
        delta = np.gradient(xy, axis=0)
        forward = delta[:, 0]*np.cos(direction) + delta[:, 1]*np.sin(direction)
        if np.any(forward <= CUSP_PROJECTION_THRESHOLD):
            warn(name, f"{name.upper()}: possible surface cusp / offset reversal.")
    xy, _ = closed_contour(surfaces)
    if has_self_intersection(xy):
        warn("contour", "Surface / edge self intersection detected.")
    return issues
