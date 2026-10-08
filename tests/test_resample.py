import numpy as np
from blade_designer.geometry.resample import closed_contour, resample_segment
from blade_designer.models.geometry import BladeSegment


def test_default_points(default_blade):
    s = default_blade.surfaces
    assert [len(getattr(s,n).x) for n in ("le","ps","te","ss")] == [21,101,21,101]
    xy, labels = closed_contour(s)
    assert len(xy) == 240 and len(np.unique(xy,axis=0)) == 240
    assert len(closed_contour(s,True)[0]) == 241
    assert labels[:20] == ["LE"]*20


def test_arc_resampling():
    s = BladeSegment(np.array([0.,.1,2.,10.]),np.zeros(4),np.array([0.,.01,.2,1.]))
    result = resample_segment(s,11)
    np.testing.assert_allclose(result.x,np.arange(11))
    np.testing.assert_allclose(result.m_norm,np.linspace(0,1,11))
