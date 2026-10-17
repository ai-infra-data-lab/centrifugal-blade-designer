"""A return bend's infinite normal must not become an upstream blade station."""
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters,TipClearanceParameters,EdgeType
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters,ArcSegmentParameters
from blade_designer.geometry.meridional_segments import generate_meridional
from blade_designer.geometry.blade_edge import project_to_wall
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.passage import calculate_passages


def folded_parameters():
    p=BladeParameters()
    p.hub=MeridionalCurveParameters(0,50,0,[LineSegmentParameters(25),ArcSegmentParameters(30,90),
        LineSegmentParameters(55),ArcSegmentParameters(20,180,True),LineSegmentParameters(50)])
    p.shroud=MeridionalCurveParameters(0,65,0,[LineSegmentParameters(25),ArcSegmentParameters(15,90),
        LineSegmentParameters(55),ArcSegmentParameters(35,180,True),LineSegmentParameters(50)])
    for side,z,r in (('hub',55,50),('shroud',40,65)):
        wall=generate_meridional(getattr(p,side))
        for name,point in (('leading_edge',[26,r]),('trailing_edge',[z,81])):
            setattr(getattr(p.impeller_edges,name),side+'_m_flow_norm',project_to_wall(wall,point)[0])
    for section in p.sections:section.edge_parameters.te_type=EdgeType.CUTOFF
    return p


@pytest.mark.parametrize('gap',[False,True])
def test_return_bend_normals_do_not_create_remote_impeller_cuts(gap):
    p=folded_parameters()
    if gap:p.tip_clearance=TipClearanceParameters(.5,1.)
    g=generate_impeller(p);result=calculate_passages(g,p.geometry.vane_count,points=101)
    assert result.stations and result.throats and not result.errors
    # The actual impeller is upstream of the return bend, not at m≈0.67.
    assert all(s.m_flow_norm<.5 for s in result.stations)


def test_local_generated_displacement_is_still_rejected():
    p=folded_parameters();g=generate_impeller(p)
    for name in ('camber','master_le','master_ps','master_te','master_ss'):
        getattr(g.sections[0],name).r+=.5
    result=calculate_passages(g,p.geometry.vane_count,points=101)
    assert any('displaced beyond' in error for error in result.errors)
