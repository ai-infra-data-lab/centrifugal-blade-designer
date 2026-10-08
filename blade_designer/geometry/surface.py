import numpy as np
from ..models.geometry import FloatArray, CamberGeometry, BladeSegment
from ..models.parameters import SurfaceMapping


def calculate_unit_tangent(x: FloatArray, y: FloatArray) -> tuple[FloatArray, FloatArray]:
    dx, dy = np.gradient(x), np.gradient(y)
    norm = np.hypot(dx, dy)
    if np.any(~np.isfinite(norm)) or np.any(norm <= 0):
        raise ValueError("Degenerate tangent.")
    return dx / norm, dy / norm


def calculate_unit_normal(tangent_x: FloatArray, tangent_y: FloatArray) -> tuple[FloatArray, FloatArray]:
    return -tangent_y, tangent_x


def resolve_mapping(camber: CamberGeometry, mapping: SurfaceMapping) -> tuple[SurfaceMapping, bool]:
    if mapping != SurfaceMapping.AUTO:
        return mapping, False
    tangent_angle = np.unwrap(camber.theta_rad + camber.rotation_sign * camber.beta_m_rad)
    turning = (tangent_angle[-1] - tangent_angle[0]) * camber.rotation_sign
    # Positive turning: pressure force towards +normal, estimated PS on -normal.
    return (SurfaceMapping.NEGATIVE_IS_PS if turning > 1e-8 else SurfaceMapping.POSITIVE_IS_PS), abs(turning) <= 1e-8


def generate_surfaces(camber: CamberGeometry, thickness: FloatArray,
                      mapping: SurfaceMapping) -> tuple[BladeSegment, BladeSegment, SurfaceMapping, bool]:
    direction = camber.theta_rad + camber.rotation_sign * camber.beta_m_rad
    nx, ny = -camber.rotation_sign * np.sin(direction), camber.rotation_sign * np.cos(direction)
    positive = BladeSegment(camber.x + thickness / 2 * nx, camber.y + thickness / 2 * ny, camber.m_norm)
    negative = BladeSegment(camber.x - thickness / 2 * nx, camber.y - thickness / 2 * ny, camber.m_norm)
    resolved, ambiguous = resolve_mapping(camber, mapping)
    ps, ss = (positive, negative) if resolved == SurfaceMapping.POSITIVE_IS_PS else (negative, positive)
    return ps, ss, resolved, ambiguous
