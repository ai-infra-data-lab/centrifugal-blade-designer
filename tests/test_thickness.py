import numpy as np
from scipy.interpolate import PchipInterpolator
from blade_designer.geometry.thickness import generate_thickness, thickness_interpolator
from blade_designer.models.parameters import ThicknessParameters, DistributionPoint


def test_control_points_and_end_slopes():
    p = ThicknessParameters()
    m = np.array([point.m_norm for point in p.points])
    np.testing.assert_allclose(generate_thickness(m,p), [1,4,1])
    np.testing.assert_allclose(thickness_interpolator(p).derivative()([0,1]),
                              PchipInterpolator(m,[1,4,1]).derivative()([0,1]))
    values = generate_thickness(np.linspace(0,1,2001),p)
    assert values.min() >= 0 and values.max() <= 4 + 1e-12


def test_arbitrary_nonnegative_distribution():
    p = ThicknessParameters([DistributionPoint(m,t) for m,t in [(0,0),(.1,2),(.3,0),(.7,8),(1,0)]])
    assert generate_thickness(np.linspace(0,1,10001),p).min() >= 0
