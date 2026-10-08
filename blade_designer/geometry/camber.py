import numpy as np
from scipy.integrate import cumulative_trapezoid
from ..models.parameters import BladeParameters
from ..models.geometry import CamberGeometry
from .distributions import generate_m_norm, generate_radius, interpolate_beta_m_deg
from .meridional import calculate_meridional

MASTER_POINTS = 2001


def generate_camber(params: BladeParameters, n_points: int = MASTER_POINTS) -> CamberGeometry:
    g = params.geometry
    r = generate_radius(generate_m_norm(n_points), g.r_le, g.r_te)
    m, m_norm = calculate_meridional(r, np.zeros_like(r))
    beta = np.deg2rad(interpolate_beta_m_deg(m_norm, params.blade_angle.points))
    sign = params.rotation_direction.sign
    theta = np.deg2rad(g.theta_le_deg) + sign * cumulative_trapezoid(np.tan(beta) / r, m, initial=0.)
    return CamberGeometry(m_norm, m, r, theta, beta, r * np.cos(theta), r * np.sin(theta), sign)
