import numpy as np
import pytest
from blade_designer.geometry.annulus import generate_annulus, rotate_xy


def test_pitch_rotation(default_blade):
    blades = generate_annulus(default_blade,20)
    assert len(blades) == 20
    assert np.rad2deg(blades[1].angle_rad) == pytest.approx(18)
    x,y = rotate_xy(blades[0].x,blades[0].y,np.pi/10)
    np.testing.assert_allclose(blades[1].x,x)
    np.testing.assert_allclose(blades[1].y,y)
