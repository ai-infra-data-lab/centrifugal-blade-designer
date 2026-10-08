import numpy as np
import pytest
from blade_designer.models.meridional import *
from blade_designer.geometry.meridional_segments import generate_meridional, validate_flow_path

from blade_designer.geometry.meridional import calculate_meridional


def test_normalized_distance():
 g=generate_meridional(MeridionalCurveParameters())
 m,m_norm=calculate_meridional(g.r,g.z)
 np.testing.assert_allclose(m,np.r_[0,np.cumsum(np.hypot(np.diff(g.r),np.diff(g.z)))])
 assert g.m[-1] == pytest.approx(sum(s.length for s in g.segments),rel=1e-14)
 assert np.all(g.m >= m-1e-10)  # Chords approach exact arc length from below.
 assert g.m[-1]-m[-1] < 0.001
 assert np.all(np.diff(m)>0)
 assert m_norm[0]==0 and m_norm[-1]==1
 le,te=m[40],m[-40]
 blade=(m[40:-39]-le)/(te-le)
 assert blade[0]==0 and blade[-1]==1
