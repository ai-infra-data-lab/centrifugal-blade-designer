"""Original-domain invariance and independent polynomial continuation."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import BSpline
from blade_designer.geometry.surface_evaluation import fit_surface_spline
from blade_designer.geometry.spline_root_extension import extend_spline_root


@pytest.mark.parametrize('spans',[[0.,1.],[0.,.3,1.],[0.,.2,.7,1.],[0.,.1,.3,.7,1.]])
def test_original_domain_and_known_polynomial_are_preserved(spans):
    degree=min(3,len(spans)-1);t=np.linspace(0,1,17)
    rows=[np.column_stack((10+t,t*t+s**degree,np.full(len(t),s)+2*t)) for s in spans]
    source=fit_surface_spline(rows,len(t),spans=spans);old=deepcopy(source)
    extended=extend_spline_root(source,.02)
    query=np.linspace(0,1,31)
    np.testing.assert_allclose(extended.evaluate_grid(query,t),source.evaluate_grid(query,t),rtol=0,atol=3e-14)
    negative=np.array([-.02,-.01,0.])
    coefficients=np.moveaxis(extended.across(negative),1,0)
    actual=BSpline(extended.along.t,coefficients,extended.along.k,axis=1)(t)
    x,y=np.meshgrid(t,negative)
    np.testing.assert_allclose(actual,np.stack((10+x,x*x+y**degree,y+2*x),axis=-1),rtol=0,atol=3e-14)
    np.testing.assert_array_equal(source.across.c,old.across.c)
    np.testing.assert_array_equal(source.across.t,old.across.t)
    np.testing.assert_array_equal(extended.along.c,source.along.c)
    assert extended.across.t[0]==-.02 and extended.across.t[-1]==1.


@pytest.mark.parametrize('fraction',[0.,-.1,.10001,True,None,float('nan'),float('inf')])
def test_invalid_or_excessive_root_extension_rejected(fraction):
    source=fit_surface_spline([[[0,0,0],[1,0,0]],[[0,0,1],[1,0,1]]],2)
    with pytest.raises(ValueError):extend_spline_root(source,fraction)
