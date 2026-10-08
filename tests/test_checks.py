import numpy as np
from blade_designer.geometry.checks import has_self_intersection


def test_intersection():
    assert has_self_intersection(np.array([[0.,0.],[2.,2.],[0.,2.],[2.,0.]]))
    assert not has_self_intersection(np.array([[0.,0.],[2.,0.],[2.,2.],[0.,2.]]))
