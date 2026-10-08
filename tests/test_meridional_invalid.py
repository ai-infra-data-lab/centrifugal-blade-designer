import numpy as np
import pytest
from blade_designer.models.meridional import *
from blade_designer.geometry.meridional_segments import generate_meridional, validate_flow_path

@pytest.mark.parametrize("segment",[LineSegmentParameters(0),LineSegmentParameters(-1),LineSegmentParameters(float('nan')),ArcSegmentParameters(0,30),ArcSegmentParameters(10,0),ArcSegmentParameters(10,float('inf')),ArcSegmentParameters(10,360)])
def test_invalid(segment):
 with pytest.raises(ValueError): generate_meridional(MeridionalCurveParameters(0,50,0,[segment]))


def test_negative_radius_and_self_intersection():
 with pytest.raises(ValueError,match="radius"):
  generate_meridional(MeridionalCurveParameters(0,5,0,[ArcSegmentParameters(20,180,True)]))
 with pytest.raises(ValueError,match="self intersection"):
  generate_meridional(MeridionalCurveParameters(0,50,0,[ArcSegmentParameters(20,270),ArcSegmentParameters(20,180)]))


def test_hub_shroud_intersection():
 h=generate_meridional(MeridionalCurveParameters(0,50,0,[LineSegmentParameters(50)]))
 s=generate_meridional(MeridionalCurveParameters(25,25,90,[LineSegmentParameters(50)]))
 with pytest.raises(ValueError,match="Hub/Shroud"): validate_flow_path(h,s)
 validate_flow_path(generate_meridional(MeridionalCurveParameters()),generate_meridional(default_shroud()))
