from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.flow_path import FlowPathParameters, StationType
from blade_designer.geometry.flow_path import *

def test_topology_regions_and_row_coordinates():
    p=FlowPathParameters()
    assert validate_component_stations(p).tolist()==[0,.15,.85,.90,.96,1]
    assert [r.name for r in component_regions(p)]==list(REGION_NAMES)
    assert region_at(p,.88)=="Vaneless Diffuser / Gap"
    np.testing.assert_allclose(blade_row_coordinate([15,85],p,100),[0,1])
    np.testing.assert_allclose(blade_row_coordinate([90,96],p,100,"diffuser"),[0,1])

@pytest.mark.parametrize("value",[0,.85,1,float("nan"),float("inf")])
def test_invalid_station_order(value):
    p=FlowPathParameters();p.stations[1].m_flow_norm=value
    with pytest.raises(ValueError):validate_component_stations(p)

def test_station_fractions_survive_geometry_changes():
    from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
    from blade_designer.geometry.meridional_segments import generate_meridional
    p=FlowPathParameters();before=deepcopy(p)
    for length in (100,200):
        h=generate_meridional(MeridionalCurveParameters(0,50,0,[LineSegmentParameters(length)]))
        s=generate_meridional(MeridionalCurveParameters(0,70,0,[LineSegmentParameters(length)]))
        u,mean,tangent,total=sample_mean_line(h,s,np.array([p.position(k) for k in StationType]))
        np.testing.assert_allclose(mean[:,0],validate_component_stations(p)*length)
        np.testing.assert_allclose(tangent,np.tile([1,0],(6,1)))
        assert total==pytest.approx(length)
    assert p==before
