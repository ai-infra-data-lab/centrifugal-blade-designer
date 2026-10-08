import numpy as np
from blade_designer.geometry.curvature import calculate_curvature
from blade_designer.models.geometry import BladeSegment


def test_circle_signed():
    phi = np.linspace(0,1.5*np.pi,2001)
    s = BladeSegment(12*np.cos(phi),12*np.sin(phi))
    k = calculate_curvature(s)
    np.testing.assert_allclose(k,1/12,rtol=2e-5)
    reverse = BladeSegment(s.x[::-1],s.y[::-1])
    np.testing.assert_allclose(calculate_curvature(reverse),-1/12,rtol=2e-5)


def test_straight():
    np.testing.assert_allclose(calculate_curvature(BladeSegment(np.linspace(0,10,20),np.zeros(20))),0,atol=1e-12)
