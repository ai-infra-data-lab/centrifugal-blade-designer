import numpy as np
import pytest
from blade_designer.models.meridional import *
from blade_designer.geometry.meridional_segments import generate_meridional, validate_flow_path

def test_length():
 g=generate_meridional(MeridionalCurveParameters(0,50,0,[LineSegmentParameters(25),ArcSegmentParameters(20,35),ArcSegmentParameters(40,20)]))
 assert g.length == pytest.approx(25+np.deg2rad(35)*20+np.deg2rad(20)*40)
 assert g.m[-1] == pytest.approx(g.length)


def test_exact_length_independent_of_preview_resolution():
 p=MeridionalCurveParameters(0,50,0,[LineSegmentParameters(25),ArcSegmentParameters(20,90)])
 for n in (3,21,201):
  g=generate_meridional(p,points_per_segment=n)
  assert g.m[-1] == pytest.approx(25+10*np.pi,rel=1e-14)
  assert np.all(np.diff(g.m)>0)

def test_zero_physical_radius_rejected():
 with pytest.raises(ValueError,match='positive R'):
  generate_meridional(MeridionalCurveParameters(start_r=0))
