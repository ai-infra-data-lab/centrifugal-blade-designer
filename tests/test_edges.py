import numpy as np
import pytest
from blade_designer.geometry.edges import generate_edge
from blade_designer.models.parameters import EdgeType


@pytest.mark.parametrize("leading",[True,False])
@pytest.mark.parametrize("kind",list(EdgeType))
def test_edges(leading,kind):
    center, tangent, ps, ss = map(np.array, ([0.,0.],[1.,0.],[0.,2.],[0.,-2.]))
    e = generate_edge(center,tangent,ps,ss,kind,1.,leading,21)
    np.testing.assert_array_equal(e.xy[0], ss if leading else ps)
    np.testing.assert_array_equal(e.xy[-1], ps if leading else ss)
    if kind != EdgeType.CUTOFF:
        np.testing.assert_allclose(np.hypot(e.x,e.y),2,atol=2e-6)
        assert e.x[10] == pytest.approx(-2 if leading else 2)
    else:
        np.testing.assert_allclose(e.x,0)


def test_ellipse_circle_equivalence_and_spacing():
    args = (np.array([0.,0.]),np.array([1.,0.]),np.array([0.,2.]),np.array([0.,-2.]))
    circle = generate_edge(*args,EdgeType.CIRCULAR,1.,True,21)
    ellipse = generate_edge(*args,EdgeType.ELLIPTICAL,1.,True,21)
    np.testing.assert_allclose(circle.xy,ellipse.xy)
    elongated = generate_edge(*args,EdgeType.ELLIPTICAL,3.,True,21)
    assert elongated.x[10] == pytest.approx(-6)
    distances = np.linalg.norm(np.diff(elongated.xy,axis=0),axis=1)
    assert distances.max()/distances.min() < 1.06


def test_join_continuity(default_blade):
    s = default_blade.master_surfaces
    np.testing.assert_array_equal(s.le.xy[0],s.ss.xy[0])
    np.testing.assert_array_equal(s.le.xy[-1],s.ps.xy[0])
    np.testing.assert_array_equal(s.te.xy[0],s.ps.xy[-1])
    np.testing.assert_array_equal(s.te.xy[-1],s.ss.xy[-1])
