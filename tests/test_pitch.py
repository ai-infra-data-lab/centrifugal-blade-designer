import numpy as np
import pytest
from blade_designer.geometry.pitch import angular_pitch, linear_pitch


def test_pitch():
    assert np.rad2deg(angular_pitch(20)) == pytest.approx(18)
    np.testing.assert_allclose(linear_pitch(np.array([100,130,160]),20),2*np.pi*np.array([100,130,160])/20)
