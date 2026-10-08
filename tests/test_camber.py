import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.camber import generate_camber
from blade_designer.geometry.designer import BladeDesigner, GeometryValidationError


@pytest.mark.parametrize("beta", [0.,45.,-45.,65.])
def test_constant_beta_m(beta):
    p = BladeParameters()
    p.geometry.theta_le_deg = 12
    for point in p.blade_angle.points:
        point.value = beta
    c = generate_camber(p)
    exact = np.deg2rad(12) + np.tan(np.deg2rad(beta))*np.log(c.r/p.geometry.r_le)
    np.testing.assert_allclose(c.theta_rad,exact,rtol=1e-4,atol=1e-6)


def test_radial():
    p = BladeParameters()
    for point in p.blade_angle.points:
        point.value = 0
    c = generate_camber(p)
    np.testing.assert_allclose(c.y,0)
    np.testing.assert_allclose(c.x,c.r)


def test_reject_invalid():
    p = BladeParameters()
    p.geometry.r_te = 90
    with pytest.raises(GeometryValidationError):
        BladeDesigner().generate(p)
