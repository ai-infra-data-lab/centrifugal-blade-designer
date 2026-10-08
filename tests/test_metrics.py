import numpy as np
import pytest


def test_metrics(default_blade):
    b = default_blade
    m = b.metrics
    assert m.angular_pitch_deg == 18
    assert m.chord == pytest.approx(np.linalg.norm(b.master_surfaces.te.xy[200]-b.master_surfaces.le.xy[200]))
    assert m.solidity_mid == pytest.approx(m.chord/(2*np.pi*130/20))
    assert m.camber_length > np.hypot(b.camber.x[-1]-b.camber.x[0],b.camber.y[-1]-b.camber.y[0])
    t = m.throat
    reference_radius = (np.hypot(t.blade1_x,t.blade1_y)+np.hypot(t.blade2_x,t.blade2_y))/2
    assert m.throat_pitch_ratio == pytest.approx(t.width/(2*np.pi*reference_radius/20))
