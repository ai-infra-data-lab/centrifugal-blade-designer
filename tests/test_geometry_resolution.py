from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.fileio.project_io import save_project,load_project

def test_configurable_internal_resolution_independent_of_export(tmp_path):
    p=BladeParameters();p.resolution.profile_points=501;p.resolution.edge_points=101
    g=generate_impeller(p)
    assert len(g.sections[0].camber.r)==501
    assert len(g.sections[0].master_le.r)==101
    assert len(BladeDesigner().generate(p).camber.r)==501
    p.output_points.ps_points=41
    changed=generate_impeller(p)
    np.testing.assert_array_equal(g.sections[0].master_ps.xyz,changed.sections[0].master_ps.xyz)
    assert len(changed.sections[0].ps.r)==41
    save_project(tmp_path/"resolution.json",p)
    assert load_project(tmp_path/"resolution.json")==p

@pytest.mark.parametrize("name,value",[("profile_points",0),("edge_points",100),("wall_points",float("nan")),("area_points",True)])
def test_invalid_resolution(name,value):
    p=BladeParameters();setattr(p.resolution,name,value)
    with pytest.raises(ValueError):generate_impeller(p)
