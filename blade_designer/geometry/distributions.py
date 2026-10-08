import numpy as np
from scipy.interpolate import PchipInterpolator
from ..models.geometry import FloatArray
from ..models.parameters import DistributionPoint


def generate_m_blade_norm(n_points: int) -> FloatArray:
    return np.linspace(0., 1., n_points)


def generate_radius(m_blade_norm: FloatArray, r_le: float, r_te: float) -> FloatArray:
    return r_le + m_blade_norm * (r_te - r_le)


def distribution_interpolator(control_m_blade_norm: FloatArray, control_values: FloatArray) -> PchipInterpolator:
    return PchipInterpolator(control_m_blade_norm, control_values, extrapolate=False)


def interpolate_distribution(m_blade_norm: FloatArray, control_m_blade_norm: FloatArray,
                             control_values: FloatArray) -> FloatArray:
    return np.asarray(distribution_interpolator(control_m_blade_norm, control_values)(m_blade_norm), dtype=np.float64)


def interpolate_beta_m_deg(m_blade_norm: FloatArray, points: list[DistributionPoint]) -> FloatArray:
    return interpolate_distribution(m_blade_norm, np.array([p.m_blade_norm for p in points]),
                                    np.array([p.value for p in points]))

# Legacy 0.2 API alias. New code uses the blade-row coordinate explicitly.
generate_m_norm = generate_m_blade_norm
