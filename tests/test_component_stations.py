from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.flow_path import StationType
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.flow_area import calculate_flow_area
from blade_designer.fileio.project_io import save_project,load_project

def test_station_aliases_and_independent_blade_positions(tmp_path):
    p=BladeParameters()
    p.flow_path.set_position(StationType.IMP_LE,.2)
    assert p.blade_le_fraction==.2
    p.blade_te_fraction=.8
    assert p.flow_path.position(StationType.IMP_TE)==.8
    g=generate_impeller(p)
    area=calculate_flow_area(g.hub,g.shroud,p.flow_path)
    from blade_designer.geometry.blade_edge import edge_endpoints
    for edge,index in ((p.impeller_edges.leading_edge,0),(p.impeller_edges.trailing_edge,-1)):
        for section,expected in zip(g.sections,edge_endpoints(edge,g.hub,g.shroud)):
            np.testing.assert_allclose([section.camber.z[index],section.camber.r[index]],expected,atol=3e-6)
    unchanged=deepcopy(p);unchanged.blade_le_fraction=.15;unchanged.blade_te_fraction=.85
    original=generate_impeller(unchanged)
    for a,b in zip(g.sections,original.sections):np.testing.assert_array_equal(a.camber.xyz,b.camber.xyz)
    save_project(tmp_path/"stations.json",p)
    assert load_project(tmp_path/"stations.json")==p

def test_physical_flow_and_blade_coordinates_are_distinct():
    p=BladeParameters();g=generate_impeller(p)
    for section in g.sections:
        assert section.camber.m_blade_norm[0]==0 and section.camber.m_blade_norm[-1]==1
        assert section.m[-1]>section.m[0]>0
    p.flow_path.stations[3].m_flow_norm=.8
    with pytest.raises(ValueError,match="Stations"):generate_impeller(p)
