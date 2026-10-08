import numpy as np
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.geometry.meridional_segments import generate_meridional
from blade_designer.geometry.flow_area import calculate_flow_area

def test_radial_annulus_analytic_area():
    h=generate_meridional(MeridionalCurveParameters(20,50,90,[LineSegmentParameters(100)]))
    s=generate_meridional(MeridionalCurveParameters(0,50,90,[LineSegmentParameters(100)]))
    result=calculate_flow_area(h,s)
    for p in result.stations:
        np.testing.assert_allclose(p.gross_area,2*np.pi*p.r_mean*20,rtol=1e-13)
        np.testing.assert_allclose([p.hub_r,p.shroud_r],[p.r_mean,p.r_mean],rtol=1e-13)
    assert np.all(np.diff([p.gross_area for p in result.stations])>0)
