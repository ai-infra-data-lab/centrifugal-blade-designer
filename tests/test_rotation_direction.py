from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters,RotationDirection,SurfaceMapping,EdgeType
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.fileio.project_io import save_project,load_project

@pytest.mark.parametrize("mapping",list(SurfaceMapping))
@pytest.mark.parametrize("edge",list(EdgeType))
def test_rotation_mirrors_actual_coordinates(mapping,edge):
    p=BladeParameters();p.surface_mapping=mapping;p.geometry.theta_le_deg=17
    for section in p.sections:section.edge_parameters.le_type=section.edge_parameters.te_type=edge
    before=deepcopy(p.sections)
    engine=BladeDesigner();ccw=engine.generate(p);a=engine.generate_3d(p)
    p.rotation_direction=RotationDirection.CW
    cw=engine.generate(p);b=engine.generate_3d(p)
    angle=np.deg2rad(34);matrix=np.array([[np.cos(angle),np.sin(angle)],[np.sin(angle),-np.cos(angle)]])
    for name in ("ps","ss","le","te"):
        np.testing.assert_allclose(getattr(cw.master_surfaces,name).xy,getattr(ccw.master_surfaces,name).xy@matrix.T,atol=1e-9)
    for first,last in zip(a.sections,b.sections):
        for name in ("camber","master_ps","master_ss","master_le","master_te"):
            x,y=getattr(first,name),getattr(last,name)
            np.testing.assert_allclose(y.r,x.r,atol=1e-10)
            np.testing.assert_allclose(y.z,x.z,atol=1e-10)
            np.testing.assert_allclose(y.theta_rad,2*np.deg2rad(17)-x.theta_rad,atol=1e-10)
    assert p.sections==before

def test_rotation_roundtrip(tmp_path):
    p=BladeParameters();p.rotation_direction=RotationDirection.CW
    save_project(tmp_path/"cw.json",p)
    assert load_project(tmp_path/"cw.json").rotation_direction is RotationDirection.CW

@pytest.mark.parametrize("axis,order",[("Z",[0,1,2]),("X",[2,0,1]),("Y",[1,2,0])])
def test_export_uses_rotated_coordinates(tmp_path,axis,order):
    from blade_designer.fileio.turbogrid_export import export_turbogrid
    p=BladeParameters();p.turbogrid.rotation_axis=axis;p.export.significant_digits=15
    first=export_turbogrid(tmp_path/"ccw",p)
    p.rotation_direction=RotationDirection.CW
    last=export_turbogrid(tmp_path/"cw",p)
    def read(path):
        return np.array([[float(v) for v in line.split()[:3]] for line in path.read_text().splitlines() if not line.startswith("#")])
    a,b=read(first[2]),read(last[2])
    expected=a[:,np.argsort(order)];expected[:,1]*=-1
    np.testing.assert_allclose(b,expected[:,order],atol=1e-12)
    np.testing.assert_array_equal(read(first[0]),read(last[0]))
