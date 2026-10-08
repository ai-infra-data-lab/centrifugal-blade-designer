import numpy as np
import pytest
from blade_designer.geometry.throat import closest_on_segments, calculate_throat
from blade_designer.models.geometry import BladeSegment
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.designer import BladeDesigner


def test_parallel_lines():
    a = BladeSegment(np.linspace(0,10,31),np.zeros(31))
    b = BladeSegment(np.linspace(2,8,27),np.full(27,3.))
    width,p,q,_,_ = closest_on_segments(a,b)
    assert width == pytest.approx(3,abs=1e-9)
    assert np.linalg.norm(p-q) == pytest.approx(width)


def test_continuous_minimum_between_samples():
    t = np.linspace(-2,2,202)
    a = BladeSegment(t,t*t+2)
    b = BladeSegment(np.array([-.1,.1]),np.zeros(2))
    width,p,q,_,_ = closest_on_segments(a,b)
    assert width == pytest.approx(2,abs=2e-7)
    assert np.min(a.y) > width + 1e-5
    assert abs(p[0]) < 1e-5


def test_crossing():
    a = BladeSegment(np.array([-1.,1.]),np.array([-1.,1.]))
    b = BladeSegment(np.array([-1.,1.]),np.array([1.,-1.]))
    assert closest_on_segments(a,b)[0] < 1e-8


def test_output_resolution_independence(default_blade):
    p = BladeParameters()
    p.output_points.ps_points = 17
    p.output_points.ss_points = 28
    p.output_points.le_points = 6
    p.output_points.te_points = 8
    other = BladeDesigner().generate(p)
    assert other.metrics.throat.width == pytest.approx(default_blade.metrics.throat.width,abs=1e-12)
    np.testing.assert_array_equal(other.curvature.ps_curvature,default_blade.curvature.ps_curvature)


def test_single_blade(default_blade):
    assert calculate_throat(default_blade.master_surfaces,1) is None


def test_radial_capsules_known_adjacent_clearance():
    p = BladeParameters()
    for point in p.blade_angle.points:
        point.value = 0.
    for point in p.thickness.points:
        point.value = 1.
    b = BladeDesigner().generate(p)
    exact = 2*p.geometry.r_le*np.sin(np.pi/p.geometry.vane_count)-1.
    assert b.metrics.throat.width == pytest.approx(exact, abs=1e-6)
