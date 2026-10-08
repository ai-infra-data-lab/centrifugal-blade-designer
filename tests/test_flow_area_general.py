from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.meridional import *
from blade_designer.geometry.meridional_segments import generate_meridional
from blade_designer.geometry.flow_area import calculate_flow_area

def test_general_diagonal_and_small_perturbation():
    angle=35.;t=np.array([np.cos(np.deg2rad(angle)),np.sin(np.deg2rad(angle))])
    n=np.array([-t[1],t[0]])
    p=MeridionalCurveParameters(0,50,angle,[LineSegmentParameters(100)])
    q=MeridionalCurveParameters(*(np.array([0,50])+20*n),angle,[LineSegmentParameters(100)])
    h,s=generate_meridional(p),generate_meridional(q)
    area=calculate_flow_area(h,s)
    for station in area.stations:
        assert station.gross_area==pytest.approx(2*np.pi*station.r_mean*20,rel=1e-12)
        assert station.passage_length==pytest.approx(20)
        # Actual intersections lie in the local normal plane.
        np.testing.assert_allclose((np.array([station.shroud_z,station.shroud_r])-np.array([station.hub_z,station.hub_r]))@t,0,atol=1e-12)
    q.start_r+=1e-4
    changed=calculate_flow_area(h,generate_meridional(q),strict=False)
    baseline={a.m_flow_norm:a.gross_area for a in area.stations}
    assert max(abs(baseline[b.m_flow_norm]-b.gross_area) for b in changed.stations)<.1

def test_line_arc_default_has_finite_smooth_area():
    p=BladeParameters()
    result=calculate_flow_area(generate_meridional(p.hub),generate_meridional(p.shroud))
    values=np.array([s.gross_area for s in result.stations])
    assert np.isfinite(values).all() and (values>0).all()
    assert np.all(np.diff([s.m for s in result.stations])>0)
    assert max(abs(np.diff(values)))<100

def test_finite_wall_end_not_extrapolated():
    h=generate_meridional(MeridionalCurveParameters(0,50,0,[LineSegmentParameters(100)]))
    s=generate_meridional(MeridionalCurveParameters(0,70,0,[LineSegmentParameters(150)]))
    with pytest.raises(ValueError,match="finite walls"):calculate_flow_area(h,s)
    partial=calculate_flow_area(h,s,strict=False)
    assert partial.errors and partial.named_stations["OUTLET"] is None
    assert all(np.isfinite(p.gross_area) for p in partial.stations)

def test_curved_concentric_arc_area_uses_exact_intersections():
    # Center (0,100), radii 50 and 30. Mean radius around that center is 40.
    h=generate_meridional(MeridionalCurveParameters(0,50,0,[ArcSegmentParameters(50,90)]),3)
    s=generate_meridional(MeridionalCurveParameters(0,70,0,[ArcSegmentParameters(30,90)]),7)
    area=calculate_flow_area(h,s)
    for p in area.stations:
        assert p.passage_length==pytest.approx(20,rel=1e-12)
        assert p.gross_area==pytest.approx(2*np.pi*p.r_mean*20,rel=1e-12)
