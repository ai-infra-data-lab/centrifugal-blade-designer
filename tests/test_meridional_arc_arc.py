import numpy as np
import pytest
from blade_designer.models.meridional import *
from blade_designer.geometry.meridional_segments import generate_meridional, validate_flow_path

def test_arc_arc():
 g=generate_meridional(MeridionalCurveParameters(0,50,0,[ArcSegmentParameters(20,35),ArcSegmentParameters(40,20)]))
 a,b=g.segments
 np.testing.assert_allclose(a.end.zr,b.start.zr)
 assert a.end_tangent@b.start_tangent == pytest.approx(1,abs=1e-14)
