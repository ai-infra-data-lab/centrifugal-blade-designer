import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import threading
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter,QColor
from blade_designer.gui.preview_3d import Preview3D
from blade_designer.gui.surface_render import SurfaceRenderQueue,SurfaceFrame,render_surface_image


def wait_until(predicate,app=None):
    deadline=time.monotonic()+5
    while not predicate() and time.monotonic()<deadline:
        if app is not None:app.processEvents()
        time.sleep(.002)
    assert predicate()


def test_queue_keeps_only_latest_request_and_rejects_old_completion():
    started=threading.Event();release=threading.Event();calls=[];queue=None
    def render(frame,token):
        calls.append(frame)
        if frame=='old':started.set();assert release.wait(3)
        return QImage(4,4,QImage.Format.Format_ARGB32)
    queue=SurfaceRenderQueue(render)
    try:
        queue.request(('old',),'old');assert started.wait(3)
        queue.request(('middle',),'middle');queue.request(('new',),'new')
        release.set()
        wait_until(lambda:queue._future.done());queue.poll()
        assert queue.image_key is None
        wait_until(lambda:queue._future.done());queue.poll()
        assert calls==['old','new'] and queue.image_key==('new',)
    finally:release.set();queue.shutdown()


def test_queue_close_is_nonblocking_and_does_not_accept_finished_image():
    started=threading.Event();release=threading.Event()
    def render(frame,token):
        started.set();assert release.wait(3)
        return QImage(4,4,QImage.Format.Format_ARGB32)
    queue=SurfaceRenderQueue(render)
    try:
        queue.request(('old',),None);assert started.wait(3)
        begin=time.monotonic();queue.shutdown();assert time.monotonic()-begin<.5
        queue.request(('forbidden',),None);release.set()
        wait_until(lambda:queue._future.done());queue.poll()
        assert queue.image is None and queue.desired_key is None and not queue.busy
    finally:release.set();queue.shutdown()


def test_worker_failure_is_reported_and_next_request_can_recover():
    def render(frame,token):
        if frame=='bad':raise ValueError('intentional render failure')
        return QImage(4,4,QImage.Format.Format_ARGB32)
    queue=SurfaceRenderQueue(render)
    try:
        queue.request(('bad',),'bad');wait_until(lambda:queue._future.done());queue.poll()
        assert queue.error=='intentional render failure' and queue.image is None
        queue.request(('good',),'good');wait_until(lambda:queue._future.done());queue.poll()
        assert queue.error is None and queue.image_key==('good',)
    finally:queue.shutdown()


def test_return_to_cached_camera_cancels_other_pending_frame():
    started=threading.Event();release=threading.Event()
    def render(frame,token):
        if frame=='moving':started.set();assert release.wait(3)
        return QImage(4,4,QImage.Format.Format_ARGB32)
    queue=SurfaceRenderQueue(render)
    try:
        queue.request(('cached',),'cached');wait_until(lambda:queue._future.done());queue.poll()
        image=queue.image;queue.request(('moving',),'moving');assert started.wait(3)
        queue.request(('pending',),'pending');assert queue.reuse(('cached',))
        release.set();wait_until(lambda:queue._future.done());queue.poll()
        assert queue.image is image and queue.image_key==('cached',) and not queue.busy
    finally:release.set();queue.shutdown()


@pytest.fixture
def view():
    app=QApplication.instance() or QApplication([])
    view=Preview3D();view.resize(600,420);view._surface_async_threshold=0
    yield app,view
    view._surface_render.shutdown();view.close();view.deleteLater();app.processEvents()


def mesh():
    return {'triangles':{'BLADE_PS':[[[-30,-20,0],[25,-20,0],[0,30,0]]],
        'ROOT_FILLET':[[[-25,-15,1],[20,-15,1],[0,25,1]]]},
        'scope':'blade_only','snapshot_hash':'test','blade_count':3,'fillet_radius_mm':1,'edges':[]}


@pytest.mark.parametrize('ratio',[1.,1.5,2.])
def test_worker_image_matches_existing_synchronous_painter_and_preserves_source(view,ratio):
    app,v=view;v.set_cad_mesh(mesh());right,up,_=v._view_basis();camera=v.camera_position
    visible=list(v.visible_surfaces());faces=np.concatenate([rows for rows,_ in visible]);before=faces.copy()
    colors=tuple(color for rows,color in visible for _ in rows);factor=2.
    frame=SurfaceFrame(faces,colors,camera['center'].copy(),camera['pan'].copy(),right.copy(),up.copy(),
        factor,v.width(),v.height(),v._plot_top,ratio)
    image=render_surface_image(frame,threading.Event())
    reference=QImage(image.size(),image.format());reference.setDevicePixelRatio(ratio);reference.fill(QColor('#101c2b'))
    painter=QPainter(reference);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipRect(0,v._plot_top,v.width(),v.height()-v._plot_top-25)
    Preview3D._paint_surfaces_sync(v,painter,camera,right,up,factor);painter.end()
    assert bytes(image.constBits())==bytes(reference.constBits())
    np.testing.assert_array_equal(faces,before)


def test_cancelled_image_does_not_paint(view):
    token=threading.Event();token.set()
    assert render_surface_image(None,token) is None


def test_camera_and_visibility_create_new_frames_without_changing_design(view):
    app,v=view;data=mesh();before=deepcopy(data);v.set_cad_mesh(data);v.show();v._show_fit.stop()
    camera=deepcopy(v.camera_position)
    def ready():return v._surface_render.image_key==v._surface_frame_key(v._surface_scene_key())
    wait_until(ready,app);original=v._surface_render.image_key
    for k,value in camera.items():np.testing.assert_array_equal(v.camera_position[k],value)
    v.camera_position['azimuth']+=25;v.update();wait_until(ready,app)
    assert v._surface_render.image_key!=original;original=v._surface_render.image_key
    v.cad_controls['root'].setChecked(False);app.processEvents();wait_until(ready,app)
    assert v._surface_render.image_key!=original and data==before
    assert all(not a.flags.writeable for a in v._surface_cache[1:2])


def test_stale_design_hides_mesh_and_cancels_pending_request(view):
    app,v=view;v.set_cad_mesh(mesh());v.show();v._show_fit.stop();app.processEvents()
    v.sync_cad_snapshot('different-design');app.processEvents()
    assert not v._cad_visible and v._surface_render.desired_key is None


def test_hide_cancels_and_show_can_render_again(view):
    app,v=view;v.set_cad_mesh(mesh());v.show();v._show_fit.stop();app.processEvents()
    v.hide();app.processEvents();assert v._surface_render.desired_key is None
    v.camera_position['azimuth']+=10;v.show();v._show_fit.stop()
    wait_until(lambda:v._surface_render.image_key==v._surface_frame_key(v._surface_scene_key()),app)


def test_same_payload_object_reinstalled_invalidates_cached_surface(view):
    app,v=view;data=mesh();v.set_cad_mesh(data);v.show();v._show_fit.stop()
    wait_until(lambda:v._surface_render.image_key==v._surface_frame_key(v._surface_scene_key()),app)
    before=v._surface_render.image_key
    data['triangles']['BLADE_PS'][0][0][0]+=10
    v.set_cad_mesh(data);app.processEvents()
    wait_until(lambda:v._surface_render.image_key==v._surface_frame_key(v._surface_scene_key()),app)
    assert v._surface_render.image_key!=before


@pytest.mark.parametrize('scope',['blade_only','blade_hub','periodic_sector','full_impeller','disk_only'])
def test_readonly_cache_arrays_support_overlay_scopes_and_empty_roles(view,tmp_path,scope):
    import json
    from blade_designer.cad.preview_cache import write_preview_cache,read_preview_cache
    app,v=view;data=mesh();data['scope']=scope;data['triangles']['EMPTY']=[]
    if scope=='disk_only':data['triangles']={'HUB_DISK':data['triangles']['BLADE_PS'],'EMPTY':[]}
    (tmp_path/'preview.json').write_text(json.dumps(data),encoding='utf-8');write_preview_cache(data,tmp_path)
    v.set_cad_mesh(read_preview_cache(tmp_path))
    for full in (False,True):
        v.cad_controls['full'].setChecked(full)
        surfaces=list(v.visible_surfaces());assert surfaces
        assert all(np.isfinite(rows).all() and rows.shape[1:]==(4,3) for rows,_ in surfaces)


def test_cache_preserves_canonical_json_layer_order_for_equal_depth(view,tmp_path):
    """Synthetic overlapping polygons check compositing, not solid validity."""
    import hashlib,json
    from blade_designer.cad.client import json_text
    from blade_designer.cad.preview_cache import write_preview_cache,read_preview_cache
    app,v=view;data=mesh();triangle=data['triangles']['BLADE_PS']
    data['triangles']={'ROOT_FILLET':triangle,'HUB_DISK':triangle,'BLADE_PS':triangle}
    text=json_text(data);(tmp_path/'preview.json').write_text(text,encoding='utf-8')
    write_preview_cache(data,tmp_path)
    legacy=json.loads(text);cached=read_preview_cache(tmp_path)
    def pixels(payload):
        v.set_cad_mesh(payload);right,up,_=v._view_basis()
        image=QImage(v.size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(QColor('#101c2b'))
        painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(0,v._plot_top,v.width(),v.height()-v._plot_top-25)
        v._paint_surfaces_sync(painter,v.camera_position,right,up,2.);painter.end()
        return hashlib.sha256(image.constBits()).hexdigest()
    assert pixels(cached)==pixels(legacy)
    assert list(cached['triangles'])==list(legacy['triangles'])
