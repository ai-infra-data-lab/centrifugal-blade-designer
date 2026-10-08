import numpy as np
from ..models.geometry import CamberGeometry, BladeMetrics, ThroatResult, FloatArray
from .pitch import angular_pitch, linear_pitch


def calculate_metrics(camber: CamberGeometry, nose: FloatArray, tail: FloatArray,
                      vane_count: int, throat: ThroatResult | None) -> BladeMetrics:
    chord = float(np.linalg.norm(tail - nose))
    length = float(np.hypot(np.diff(camber.x), np.diff(camber.y)).sum())
    radii = np.interp([0., .5, 1.], camber.m_norm, camber.r)
    pitches = linear_pitch(radii, vane_count)
    solidity = chord / pitches
    throat_pitch = None
    if throat is not None:
        r_throat = (np.hypot(throat.blade1_x, throat.blade1_y) + np.hypot(throat.blade2_x, throat.blade2_y)) / 2
        throat_pitch = float(linear_pitch(r_throat, vane_count))
    return BladeMetrics(chord, length, float(np.rad2deg(angular_pitch(vane_count))),
                        *map(float, pitches), *map(float, solidity), throat, throat_pitch,
                        None if throat is None or throat_pitch == 0 else throat.width / throat_pitch)
