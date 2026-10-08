import numpy as np
from scipy.interpolate import PchipInterpolator
from .distributions import distribution_interpolator, interpolate_distribution
from ..models.geometry import FloatArray
from ..models.parameters import ThicknessParameters


def thickness_interpolator(params: ThicknessParameters) -> PchipInterpolator:
    return distribution_interpolator(np.array([p.m_blade_norm for p in params.points]),
                                    np.array([p.value for p in params.points]))


def generate_thickness(m_blade_norm: FloatArray, params: ThicknessParameters) -> FloatArray:
    values = interpolate_distribution(m_blade_norm, np.array([p.m_blade_norm for p in params.points]),
                                      np.array([p.value for p in params.points]))
    if np.any(~np.isfinite(values)) or np.any(values < -1e-12):
        raise ValueError("Interpolated thickness is negative or non-finite.")
    return np.maximum(values, 0.)
