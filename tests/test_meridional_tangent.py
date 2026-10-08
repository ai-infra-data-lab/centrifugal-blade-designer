import numpy as np
import pytest
from blade_designer.models.meridional import *
from blade_designer.geometry.meridional_segments import generate_meridional, validate_flow_path

def test_line_arc_line():
 g=generate_meridional(MeridionalCurveParameters(0,50,0,[LineSegmentParameters(25),ArcSegmentParameters(20,35),LineSegmentParameters(40)]))
 for a,b in zip(g.segments,g.segments[1:]):
  np.testing.assert_allclose(a.end.zr,b.start.zr,atol=1e-13)
  np.testing.assert_allclose(a.end_tangent,b.start_tangent,atol=1e-13)
