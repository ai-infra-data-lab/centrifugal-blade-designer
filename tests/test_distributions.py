import numpy as np
from blade_designer.geometry.distributions import generate_m_norm, generate_radius, interpolate_beta_m_deg
from blade_designer.models.parameters import DistributionPoint


def test_distribution():
    m = generate_m_norm(201)
    assert m[0] == 0 and m[-1] == 1
    np.testing.assert_allclose(np.diff(m), .005)
    r = generate_radius(m,100,160)
    assert r[0] == 100 and r[-1] == 160
    points = [DistributionPoint(x,y) for x,y in [(0,65),(.13,50),(.6,45),(1,30)]]
    np.testing.assert_allclose(interpolate_beta_m_deg(np.array([p.m_norm for p in points]), points), [p.value for p in points])
