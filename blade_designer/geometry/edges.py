import numpy as np
from ..models.geometry import BladeSegment, FloatArray
from ..models.parameters import EdgeType
from .resample import resample_segment

EDGE_MASTER_POINTS = 401


def generate_edge(center: FloatArray, tangent: FloatArray, ps_endpoint: FloatArray,
                  ss_endpoint: FloatArray, edge_type: EdgeType, ratio: float,
                  leading: bool, n_points: int = EDGE_MASTER_POINTS) -> BladeSegment:
    start, end = (ss_endpoint, ps_endpoint) if leading else (ps_endpoint, ss_endpoint)
    if edge_type == EdgeType.CUTOFF:
        points = np.linspace(start, end, n_points)
        return BladeSegment(points[:, 0], points[:, 1])
    b = float(np.linalg.norm(ps_endpoint - ss_endpoint) / 2)
    if b == 0:
        return BladeSegment(np.full(n_points, center[0]), np.full(n_points, center[1]))
    a = b * (ratio if edge_type == EdgeType.ELLIPTICAL else 1.)
    normal_start = (start - center) / b
    phi = np.linspace(0., np.pi, max(4001, n_points * 4 + 1))
    xy = center + b * np.cos(phi)[:, None] * normal_start + (-1 if leading else 1) * a * np.sin(phi)[:, None] * tangent
    xy[0], xy[-1] = start, end
    result = resample_segment(BladeSegment(xy[:, 0], xy[:, 1]), n_points)
    if n_points % 2:
        nose = center + (-1 if leading else 1) * a * tangent
        result.x[n_points // 2], result.y[n_points // 2] = nose
    return result
