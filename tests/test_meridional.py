import numpy as np
from blade_designer.geometry.meridional import calculate_meridional


def test_radial_meridional():
    r = np.linspace(100,160,2001)
    m, normalized = calculate_meridional(r,np.full_like(r,42))
    np.testing.assert_allclose(m,r-100)
    np.testing.assert_allclose(normalized,(r-100)/60)


def test_rz_arc_length():
    m, normalized = calculate_meridional(np.array([1.,4.,7.]),np.array([0.,4.,8.]))
    np.testing.assert_allclose(m,[0,5,10])
    np.testing.assert_allclose(normalized,[0,.5,1])
