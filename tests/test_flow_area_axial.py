import numpy as np
import pytest
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.geometry.meridional_segments import generate_meridional
from blade_designer.geometry.flow_area import calculate_flow_area

def test_axial_annulus_analytic_area():
    h=generate_meridional(MeridionalCurveParameters(0,50,0,[LineSegmentParameters(100)]))
    s=generate_meridional(MeridionalCurveParameters(0,70,0,[LineSegmentParameters(100)]),17)
    result=calculate_flow_area(h,s)
    np.testing.assert_allclose([p.gross_area for p in result.stations],np.pi*(70**2-50**2),rtol=1e-13)
    assert not result.errors
    assert len(result.named_stations)==6
    for p in result.stations:
        assert p.passage_length==pytest.approx(20)
        assert result.area_ratio(p)==pytest.approx(1)
