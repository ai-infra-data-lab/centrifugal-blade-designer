from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtCore import QPointF,Qt
from PySide6.QtGui import QPolygonF
from blade_designer.gui import preview_3d as module
from test_cad_surface_render import view,mesh


def legacy_hit(v,point):
    right,up,_=v._view_basis();c=v.camera_position;factor=min(v.width(),v.height())/(2*c['scale'])
    for faces,color in v.visible_surfaces():
        if color!='#e8bd42':continue
        for face in faces:
            relative=face-c['center'];x=(relative@right+c['pan'][0])*factor+v.width()/2
            y=-(relative@up+c['pan'][1])*factor+(v.height()+v._plot_top)/2
            if QPolygonF([QPointF(float(a),float(b)) for a,b in zip(x,y)]).containsPoint(point,Qt.FillRule.OddEvenFill):return True
    return False


@pytest.mark.parametrize('view_name',['front','top','side','iso'])
def test_pruned_fillet_hits_match_original_qt_polygon_test(view,view_name):
    app,v=view;data=mesh();v.set_cad_mesh(data);v.set_view(view_name);before=deepcopy(data)
    right,up,_=v._view_basis();c=v.camera_position;factor=min(v.width(),v.height())/(2*c['scale'])
    points=[QPointF(float(x),float(y)) for x,y in np.random.default_rng(71).uniform([0,v._plot_top],[v.width(),v.height()-25],size=(50,2))]
    for faces,color in v.visible_surfaces():
        if color=='#e8bd42':
            for face in faces:
                relative=face-c['center'];x=(relative@right+c['pan'][0])*factor+v.width()/2;y=-(relative@up+c['pan'][1])*factor+(v.height()+v._plot_top)/2
                points.extend(QPointF(float(a),float(b)) for a,b in zip(x,y));points.append(QPointF(float(np.mean(x)),float(np.mean(y))))
    assert [v._fillet_hit(p) for p in points]==[legacy_hit(v,p) for p in points]
    assert data==before


def test_fillet_broad_phase_avoids_qt_polygon_creation_for_distant_faces(view,monkeypatch):
    app,v=view;data=mesh();triangle=np.asarray(data['triangles']['ROOT_FILLET'][0])
    data['triangles']['ROOT_FILLET']=[(triangle+[100*(i%50),100*(i//50),0]).tolist() for i in range(2000)]
    v.set_cad_mesh(data);v.camera_position.update(azimuth=-90.,elevation=90.,scale=10000.,center=np.zeros(3),pan=np.zeros(2))
    right,up,_=v._view_basis();center=np.mean(triangle,axis=0);factor=min(v.width(),v.height())/20000
    point=QPointF(float(center@right*factor+v.width()/2),float(-center@up*factor+(v.height()+v._plot_top)/2))
    calls=[]
    def polygon(points):calls.append(1);return QPolygonF(points)
    monkeypatch.setattr(module,'QPolygonF',polygon)
    assert v._fillet_hit(point) and len(calls)==1
    cached=v._fillet_hit_cache;assert v._fillet_hit(point) and v._fillet_hit_cache is cached
    v.camera_position['azimuth']+=5;v._fillet_hit(point);assert v._fillet_hit_cache is not cached


@pytest.mark.parametrize('action',['hidden_root','stale_mesh','replaced_mesh'])
def test_fillet_hit_cache_obeys_visibility_and_scene_generation(view,action):
    app,v=view;v.set_cad_mesh(mesh());point=QPointF(300.,250.);v._fillet_hit(point);cached=v._fillet_hit_cache
    if action=='hidden_root':v.cad_controls['root'].setChecked(False)
    elif action=='stale_mesh':v.sync_cad_snapshot('changed')
    else:v.set_cad_mesh(mesh())
    result=v._fillet_hit(point)
    if action!='replaced_mesh':assert not result
    else:assert v._fillet_hit_cache is not cached
