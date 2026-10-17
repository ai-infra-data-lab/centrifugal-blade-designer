"""Measurements of actual sampled XYZ sections, independent of Qt and formats.

Lengths use the sampled camber polyline. Curvature is the nonnegative spatial
curvature of an interpolating cubic spline parameterized by chord arclength.
Neither quantity establishes surface continuity or a true 3D passage throat.
"""
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import CubicSpline


@dataclass(frozen=True)
class SectionMeasurements:
    span: float
    camber_chord_xyz: float
    camber_length_xyz: float
    radii: np.ndarray
    z: np.ndarray
    streamwise: np.ndarray
    pitch: np.ndarray
    ps_streamwise: np.ndarray
    ps_curvature_xyz: np.ndarray
    ss_streamwise: np.ndarray
    ss_curvature_xyz: np.ndarray


def spatial_curvature(xyz):
    points = np.asarray(xyz, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3 or not np.all(np.isfinite(points)):
        raise ValueError('XYZ curvature requires at least three finite 3D points.')
    steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
    if np.any(steps <= 0):
        raise ValueError('XYZ curvature requires distinct consecutive points.')
    s = np.r_[0., np.cumsum(steps)]
    spline = CubicSpline(s, points)
    first, second = spline(s, 1), spline(s, 2)
    speed = np.linalg.norm(first, axis=1)
    if np.any(speed < 1e-12):
        raise ValueError('XYZ curvature is undefined at a vanishing tangent.')
    return np.linalg.norm(np.cross(first, second), axis=1) / speed**3


def measure_section(section, blade_count):
    if isinstance(blade_count, bool) or not isinstance(blade_count, (int, np.integer)) or blade_count < 1:
        raise ValueError('Blade count must be an integer >= 1.')
    camber = section.camber
    xyz = camber.xyz
    if len(xyz) < 2 or not np.all(np.isfinite(xyz)) or np.any(camber.r <= 0):
        raise ValueError('Camber measurements require finite coordinates and positive radii.')
    coordinates = []
    for curve in (camber, section.master_ps, section.master_ss):
        u = np.asarray(curve.m_blade_norm, dtype=float)
        if u.ndim != 1 or len(u) != len(curve.r) or not np.all(np.isfinite(u)) or np.any(np.diff(u) <= 0):
            raise ValueError('Section measurements require increasing streamwise coordinates.')
        coordinates.append(u.copy())
    return SectionMeasurements(
        section.span, float(np.linalg.norm(xyz[-1] - xyz[0])),
        float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum()),
        camber.r.copy(), camber.z.copy(), coordinates[0], 2*np.pi*camber.r/blade_count,
        coordinates[1], spatial_curvature(section.master_ps.xyz),
        coordinates[2], spatial_curvature(section.master_ss.xyz))
