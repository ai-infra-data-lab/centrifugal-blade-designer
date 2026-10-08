import numpy as np
import pytest
from blade_designer.models.meridional import *
from blade_designer.geometry.meridional_segments import generate_meridional, validate_flow_path

@pytest.mark.parametrize("clockwise",[False,True])
def test_arc(clockwise):
 g=generate_meridional(MeridionalCurveParameters(0,50,0,[ArcSegmentParameters(20,90,clockwise)]))
 s=g.segments[0]; sign=-1 if clockwise else 1
 np.testing.assert_allclose(s.end.zr,[20,50+sign*20],atol=1e-12)
 np.testing.assert_allclose(s.end_tangent,[0,sign],atol=1e-12)
 assert s.length == pytest.approx(10*np.pi)
 np.testing.assert_allclose(np.hypot(g.z-s.center.z,g.r-s.center.r),20)
