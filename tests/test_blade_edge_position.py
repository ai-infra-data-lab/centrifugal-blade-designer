from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.blade_edge import BladeEdgePosition
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters,ArcSegmentParameters
from blade_designer.geometry.meridional_segments import generate_meridional,sample_meridional
from blade_designer.geometry.blade_edge import project_to_wall,edge_endpoints
from blade_designer.geometry.geometry_3d import generate_impeller

@pytest.mark.parametrize("value",[float("nan"),float("inf"),-.01,1.01])
@pytest.mark.parametrize("row",["impeller_edges","diffuser_edges"])
def test_invalid_endpoints(value,row):
    p=BladeParameters();getattr(p,row).leading_edge.hub_m_flow_norm=value
    with pytest.raises(ValueError,match="Blade edge"):generate_impeller(p)

def test_order_validation():
    p=BladeParameters();p.impeller_edges.trailing_edge.shroud_m_flow_norm=.1
    with pytest.raises(ValueError,match="TE > LE"):generate_impeller(p)

def test_independent_wall_endpoints():
    p=BladeParameters();p.impeller_edges.leading_edge=BladeEdgePosition(.2,.28)
    p.impeller_edges.trailing_edge=BladeEdgePosition(.72,.82)
    stations=deepcopy(p.flow_path);g=generate_impeller(p)
    assert p.flow_path==stations
    for edge,i in ((p.impeller_edges.leading_edge,0),(p.impeller_edges.trailing_edge,-1)):
        for section,zr in zip(g.sections,edge_endpoints(edge,g.hub,g.shroud)):
            np.testing.assert_allclose([section.camber.z[i],section.camber.r[i]],zr,atol=1e-10)

def test_exact_line_and_arc_projection():
    wall=generate_meridional(MeridionalCurveParameters(0,50,0,[LineSegmentParameters(20),ArcSegmentParameters(20,90)]))
    fraction,point=project_to_wall(wall,[10,54])
    np.testing.assert_allclose(point,[10,50]);assert fraction==pytest.approx(10/wall.length)
    target=sample_meridional(wall,np.array([20+20*np.pi/4]))[0]
    segment=wall.segments[1];outside=segment.center.zr+1.2*(target-segment.center.zr)
    fraction,point=project_to_wall(wall,outside)
    np.testing.assert_allclose(point,target,atol=1e-12)
    assert fraction==pytest.approx((20+20*np.pi/4)/wall.length)
    assert project_to_wall(wall,[-10,50])[0]==0

def test_crossing_le_te_lines_rejected():
    from blade_designer.geometry.blade_edge import validate_blade_edges
    from blade_designer.models.blade_edge import BladeRowEdgeParameters
    hub=generate_meridional(MeridionalCurveParameters(0,10,0,[LineSegmentParameters(100)]))
    shroud=generate_meridional(MeridionalCurveParameters(100,20,180,[LineSegmentParameters(100)]))
    with pytest.raises(ValueError,match="cross"):
        validate_blade_edges(BladeRowEdgeParameters(),hub,shroud)
