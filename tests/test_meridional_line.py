import numpy as np
import pytest
from blade_designer.models.meridional import *
from blade_designer.geometry.meridional_segments import generate_meridional, validate_flow_path

def test_line():
 g=generate_meridional(MeridionalCurveParameters(2,10,30,[LineSegmentParameters(8)]))
 np.testing.assert_allclose(g.segments[0].end.zr,[2+8*np.cos(np.pi/6),14])
 assert g.length == pytest.approx(8)
