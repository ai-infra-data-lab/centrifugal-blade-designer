from types import SimpleNamespace
from copy import deepcopy
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.geometry.revolved_surface import revolve_wall
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.models.parameters import BladeParameters
from blade_designer.gui.preview_3d import Preview3D


def test_cylinder_radius_full_revolution_and_closed_seam():
    wall=SimpleNamespace(r=np.array([10.,10.]),z=np.array([0.,20.]))
    before=deepcopy(wall)
    faces=revolve_wall(wall,angular_segments=8)
    assert faces.shape==(8,4,3)
    np.testing.assert_allclose(np.hypot(faces[:,:,0],faces[:,:,1]),10,atol=1e-12)
    assert faces[:,:,0].min()==-10 and faces[:,:,1].min()==-10
    assert faces[:,:,0].max()==10 and faces[:,:,1].max()==10
    np.testing.assert_array_equal(faces[-1,3],faces[0,0])
    np.testing.assert_array_equal(faces[-1,2],faces[0,1])
    np.testing.assert_array_equal(wall.r,before.r); np.testing.assert_array_equal(wall.z,before.z)


def test_conical_wall_and_sampling_preserve_both_ends():
    wall=SimpleNamespace(r=np.linspace(5,15,501),z=np.linspace(0,20,501))
    faces=revolve_wall(wall,max_wall_points=9,angular_segments=12)
    assert faces.shape==(8*12,4,3)
    np.testing.assert_allclose(np.hypot(faces[:,:,0],faces[:,:,1]),5+faces[:,:,2]/2,atol=1e-12)
    assert faces[:,:,2].min()==0 and faces[:,:,2].max()==20


@pytest.mark.parametrize("wall",[
    SimpleNamespace(r=np.array([-1.,2.]),z=np.array([0.,1.])),
    SimpleNamespace(r=np.array([1.,np.nan]),z=np.array([0.,1.])),
    SimpleNamespace(r=np.array([1.,2.]),z=np.array([0.])),
])
def test_invalid_surface_is_rejected(wall):
    with pytest.raises(ValueError):revolve_wall(wall)


def test_wall_surface_visibility_annulus_camera_and_diffuser():
    app=QApplication.instance() or QApplication([])
    p=BladeParameters(); g=generate_impeller(p); preview=Preview3D()
    try:
        preview.update_geometry(g)
        before=deepcopy(preview.surfaces); camera=deepcopy(preview.camera_position)
        assert len(list(preview.visible_surfaces()))==2
        assert len(list(preview.visible_lines()))==254
        preview.visibility_controls["hub"].setChecked(False)
        assert len(list(preview.visible_surfaces()))==1
        preview.visibility_controls["shroud"].setChecked(False)
        assert list(preview.visible_surfaces())==[]
        preview.visibility_controls["hub"].setChecked(True)
        preview.visibility_controls["shroud"].setChecked(True)
        preview.set_full_annulus(True,11)
        for key in before:np.testing.assert_array_equal(preview.surfaces[key][0],before[key][0])
        preview.update_diffuser(BladeDesigner().generate_diffuser_3d(p))
        for key in before:np.testing.assert_array_equal(preview.surfaces[key][0],before[key][0])
        for key,value in camera.items():np.testing.assert_array_equal(preview.camera_position[key],value)
        preview.close()
    finally:
        preview.deleteLater(); app.processEvents()


@pytest.mark.parametrize("azimuth,elevation",[(-45,25),(0,0),(90,70)])
def test_fit_view_contains_complete_revolved_surfaces(azimuth,elevation):
    app=QApplication.instance() or QApplication([]); preview=Preview3D()
    try:
        preview.resize(600,350); preview.show(); app.processEvents()
        preview.update_geometry(generate_impeller(BladeParameters()))
        preview.camera_position.update(azimuth=azimuth,elevation=elevation)
        preview.fit_view()
        xyz=np.concatenate([faces.reshape(-1,3) for faces,color in preview.surfaces.values()])
        camera=preview.camera_position; a,e=np.deg2rad([azimuth,elevation])
        right=np.array([-np.sin(a),np.cos(a),0]); up=np.array([-np.cos(a)*np.sin(e),-np.sin(a)*np.sin(e),np.cos(e)])
        factor=min(preview.width(),preview.height())/(2*camera["scale"])
        x=((xyz-camera["center"])@right+camera["pan"][0])*factor+preview.width()/2
        y=-((xyz-camera["center"])@up+camera["pan"][1])*factor+(preview.height()+60)/2
        assert x.min()>=0 and x.max()<=preview.width()
        assert y.min()>=60 and y.max()<=preview.height()-25
        image=preview.grab().toImage()
        assert not image.isNull()
    finally:
        preview.close(); preview.deleteLater(); app.processEvents()
