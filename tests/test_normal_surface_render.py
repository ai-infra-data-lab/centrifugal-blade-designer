"""Completed normal surfaces retain the original painter's actual pixels."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.gui.preview_3d import Preview3D
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.models.parameters import BladeParameters,TipClearanceParameters
from blade_designer.fileio.project_io import load_project
from test_cad_surface_render import view,wait_until,mesh


@pytest.mark.parametrize('variant',['impeller','diffuser','clearance','owned_chunks'])
def test_normal_completed_frame_matches_sync_and_preserves_design(view,variant):
    app,v=view;params=load_project('blade_designer/defaults/default_project.json')
    if variant=='clearance':
        params=BladeParameters();params.tip_clearance=TipClearanceParameters(.5,1.,.2,.3)
    before=deepcopy(params)
    geometry=generate_diffuser_3d(params) if variant=='diffuser' else generate_impeller(params)
    chunks={'hub':[geometry.hub],'shroud':[]} if variant=='owned_chunks' else None
    v.update_geometry(geometry,wall_chunks=chunks)
    assert not hasattr(v,'cad_controls') and not hasattr(v,'_cad_data')
    v._surface_async_threshold=10**12;v.show();app.processEvents();v._show_fit.stop()
    expected=v.grab().toImage();camera=deepcopy(v.camera_position)
    source={name:array.copy() for name,(array,color) in v.surfaces.items()}
    v._surface_async_threshold=0;v.update()
    wait_until(lambda:v._surface_render.image_key==v._surface_frame_key(v._surface_scene_key()),app)
    actual=v.grab().toImage()
    assert bytes(expected.constBits())==bytes(actual.constBits())
    assert params==before and v._surface_render.error is None
    for name,(array,color) in v.surfaces.items():np.testing.assert_array_equal(array,source[name])
    for key,value in camera.items():np.testing.assert_array_equal(value,v.camera_position[key])


def test_normal_same_object_rebuild_changes_generation_and_retains_lazy_cad(view):
    app,v=view;geometry=generate_impeller(BladeParameters());v.update_geometry(geometry)
    v.show();app.processEvents();v._show_fit.stop()
    ready=lambda:v._surface_render.image_key==v._surface_frame_key(v._surface_scene_key())
    wait_until(ready,app);old=v._surface_render.image_key
    v.update_geometry(geometry);app.processEvents();wait_until(ready,app)
    assert v._surface_render.image_key!=old and not hasattr(v,'cad_controls')
    v.set_cad_mesh(mesh());app.processEvents();wait_until(ready,app)
    assert v.cad_controls and v._cad_visible
    v.sync_cad_snapshot('another');app.processEvents();wait_until(ready,app)
    assert not v._cad_visible


@pytest.mark.parametrize('action',['camera','visibility','resize','hide_show','reference'])
def test_normal_scene_lifecycle_rejects_old_frame(view,action):
    app,v=view;geometry=generate_impeller(BladeParameters());v.update_geometry(geometry)
    v.show();app.processEvents();v._show_fit.stop()
    ready=lambda:v._surface_render.image_key==v._surface_frame_key(v._surface_scene_key())
    wait_until(ready,app);old=v._surface_render.image_key
    if action=='camera':v.camera_position['azimuth']+=15;v.update()
    elif action=='visibility':v.visibility_controls['hub'].setChecked(False)
    elif action=='resize':v.resize(640,460)
    elif action=='hide_show':
        v.hide();app.processEvents();assert v._surface_render.desired_key is None
        v.show();app.processEvents();v._show_fit.stop();v.camera_position['azimuth']+=10;v.update()
    else:
        v.update_surface_reference({},'Reference');app.processEvents()
        assert v._surface_render.desired_key is None and not v.surfaces
        return
    app.processEvents();wait_until(ready,app);assert v._surface_render.image_key!=old


def test_small_normal_surface_remains_synchronous(view):
    app,v=view;geometry=generate_impeller(BladeParameters());v.update_geometry(geometry)
    v._surface_async_threshold=10**12;v.show();app.processEvents();v._show_fit.stop()
    assert v._surface_render.desired_key is None and v._surface_cache is None


def test_all_row_scene_rebuild_invalidates_frame(view):
    app,v=view;g=generate_impeller(BladeParameters())
    rows=[('row-1','Impeller',g,3)]
    v.update_rows(rows,g);v.show();app.processEvents();v._show_fit.stop()
    ready=lambda:v._surface_render.image_key==v._surface_frame_key(v._surface_scene_key())
    wait_until(ready,app);old=v._surface_render.image_key
    v.update_rows(rows,g);app.processEvents();wait_until(ready,app)
    assert v._surface_render.image_key!=old
