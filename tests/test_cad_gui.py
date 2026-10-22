import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from dataclasses import asdict
import hashlib,json
import numpy as np
import pytest
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.cad.client import json_text
from blade_designer.models.cad import MechanicalExportScope
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters

@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([]);w=MainWindow();w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_cad_parameters_undo_project_and_missing_disk(window,tmp_path):
    w=window;before=deepcopy(w.get_parameters());w.cad_editor.radius.setValue(9);w.commit_edit()
    assert w.get_parameters().cad_export.fillet.hub_radius_mm==9
    w.undo();assert w.get_parameters()==before
    w.cad_editor.scope.setCurrentIndex(w.cad_editor.scope.findData('blade_only'));w.commit_edit()
    path=tmp_path/'cad.json';w.save_to_path(path);w.new_project();w.load_from_path(path)
    assert w.get_parameters().cad_export.mechanical_scope==MechanicalExportScope.BLADE_ONLY
    assert w.get_parameters().cad_export.disk.backside is None
    w.select_blade_row('row-2')
    assert not any(w.tabs.tabText(i)=='CAD / Fillet' and w.tabs.isTabVisible(i) for i in range(w.tabs.count()))


def test_disk_apply_undo_and_invalid_pending_save(window,tmp_path):
    w=window;p=w.get_parameters();original=deepcopy(p.cad_export.disk)
    curve=MeridionalCurveParameters(80,135,-90,[LineSegmentParameters(115)])
    w.cad_editor.backside.setPlainText(json.dumps(asdict(curve)))
    assert w.cad_editor.apply_pending_disk()
    assert w.get_parameters().cad_export.disk.backside==curve
    w.undo();assert w.get_parameters().cad_export.disk==original
    path=tmp_path/'p.json';w.save_to_path(path);prior=path.read_bytes()
    w.cad_editor.backside.setPlainText('{invalid')
    with pytest.raises(ValueError):w.save_to_path(path)
    assert path.read_bytes()==prior


def test_cad_precision_and_optional_backend_do_not_change_geometry(window):
    w=window;p=w.get_parameters();p.cad_export.fillet.hub_radius_mm=8.12345678901234
    w.set_parameters(p);w.update_geometry();before=w.impeller_geometry.sections[0].ps.xyz.copy()
    assert w.get_parameters().cad_export.fillet.hub_radius_mm==p.cad_export.fillet.hub_radius_mm
    w.cad_editor.radius.setValue(8);w.commit_edit();w.update_geometry()
    np.testing.assert_array_equal(w.impeller_geometry.sections[0].ps.xyz,before)


def test_worker_snapshot_and_stale_mesh_keep_camera(window,monkeypatch):
    from blade_designer.gui import main_window
    class FakeWorker(QObject):
        progress=Signal(str);completed=Signal(object)
        def __init__(self,job,parent):super().__init__(parent);self.job=job
        def start(self):pass
        def cancel(self):pass
    monkeypatch.setattr(main_window,'CadExportWorker',FakeWorker)
    w=window;w.cad_editor.scope.setCurrentIndex(w.cad_editor.scope.findData('blade_only'))
    before=deepcopy(w.get_parameters());camera=deepcopy(w.model_preview_3d.camera_position)
    w.start_cad_job('generate');worker=w._cad_worker;assert worker is not None
    source=json.loads((worker.job/'geometry_snapshot.json').read_text(encoding='utf-8'));assert source['geometry']==asdict(before.geometry)
    digest=hashlib.sha256(json_text(source).encode('utf-8')).hexdigest()
    triangle=[[[60,0,0],[61,0,0],[60,1,0]]]
    (worker.job/'preview.json').write_text(json_text({'triangles':{'BLADE_PS':triangle},'snapshot_hash':digest,'scope':'blade_only','blade_count':20,'fillet_radius_mm':8,'edges':[]}),encoding='utf-8')
    w.angle_editor.move_point(1,.25,45);w.update_geometry();worker.completed.emit({'overall':'WARNING','artifacts':{}})
    assert not w.model_preview_3d._cad_visible
    assert w.model_preview_3d.visibility_controls['profiles'].isChecked()
    for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)
    w.set_parameters(before);w.update_geometry();assert w.model_preview_3d._cad_visible
    assert not w.model_preview_3d.visibility_controls['profiles'].isChecked()
    w.model_preview_3d.cad_controls['full'].setChecked(True)
    assert sum(len(faces) for faces,color in w.model_preview_3d.visible_surfaces() if color=='#75c6fa')==20


def test_periodic_cad_preview_keeps_sector_until_full_selected(window):
    view=window.model_preview_3d
    def triangles(x):return {'BLADE_PS':[[[x,0,0],[x+1,0,0],[x,1,0]]]}
    view.set_cad_mesh({'triangles':triangles(60),'triangles_single':triangles(70),
        'triangles_full':triangles(80),'snapshot_hash':'test','scope':'periodic_sector',
        'blade_count':2,'fillet_radius_mm':8,'edges':[]})
    blade=lambda:next(faces for faces,color in view.visible_surfaces() if color=='#75c6fa')
    assert blade()[0,0,0]==60
    view.cad_controls['full'].setChecked(True)
    assert blade()[0,0,0]==80
    view.cad_controls['full'].setChecked(False)
    assert blade()[0,0,0]==60


def test_root_radius_typed_commit_and_provisional_disk_undo_save(window,tmp_path):
    w=window;before=deepcopy(w.get_parameters())
    w.cad_editor.radius.lineEdit().setText('2.5')
    assert w.get_parameters().cad_export.fillet.hub_radius_mm==8
    assert w.cad_editor.apply_pending_disk()
    assert w.get_parameters().cad_export.fillet.hub_radius_mm==2.5
    w.undo();assert w.get_parameters()==before
    assert w._create_provisional_disk()
    p=deepcopy(w.get_parameters());assert p.cad_export.disk.provisional
    assert 'PROVISIONAL' in w.cad_editor.disk_kind.text()
    assert p.cad_export.disk.bore_radius_mm==10
    w.undo();assert w.get_parameters()==before
    w.redo();assert w.get_parameters()==p
    path=tmp_path/'disk.json';w.save_to_path(path);w.new_project();w.load_from_path(path)
    assert w.get_parameters().cad_export.disk==p.cad_export.disk
    w.cad_editor.bore_known.setChecked(False)
    assert 'PROVISIONAL' in w.cad_editor.disk_kind.text()


def test_manual_disk_is_preserved_and_missing_disk_auto_created(window,monkeypatch):
    from blade_designer.gui import main_window
    w=window;p=w.get_parameters()
    p.cad_export.disk.backside=MeridionalCurveParameters(-20,135,-90,[LineSegmentParameters(125)])
    p.cad_export.disk.bore_radius_mm=10
    w.set_parameters(p);before=deepcopy(w.get_parameters())
    assert not w._create_provisional_disk() and w.get_parameters()==before
    w.new_project();jobs=[]
    class FakeWorker(QObject):
        progress=Signal(str);completed=Signal(object)
        def __init__(self,job,parent):super().__init__(parent);self.job=job;jobs.append(job)
        def start(self):self.completed.emit({'overall':'WARNING','artifacts':{}})
    monkeypatch.setattr(main_window,'CadExportWorker',FakeWorker)
    w.start_cad_job('generate')
    assert len(jobs)==1
    request=json.loads((jobs[0]/'request.json').read_text(encoding='utf-8'))
    assert request['settings']['disk']['provisional'] and request['mechanical_hub_segments']
    w.cad_editor.provisional_disk.click()
    request=json.loads((jobs[-1]/'request.json').read_text(encoding='utf-8'))
    assert request['action']=='disk'


def test_disk_only_preview_keeps_current_blade_wireframe(window):
    view=window.model_preview_3d
    before={key:box.isChecked() for key,box in view.visibility_controls.items()}
    view.set_cad_mesh({'triangles':{'HUB_DISK':[[[60,0,0],[61,0,0],[60,1,0]]]},
        'snapshot_hash':'disk','scope':'disk_only','blade_count':11,'fillet_radius_mm':8,'edges':[]})
    assert {key:box.isChecked() for key,box in view.visibility_controls.items()}==before
    assert not view.cad_controls['root'].isEnabled()
    assert not view.cad_controls['blade'].isEnabled()


def test_invalid_preview_is_reported_and_worker_cleanup_preserves_design(window,tmp_path):
    w=window;before=deepcopy(w.get_parameters());worker=QObject(w);w._cad_worker=worker
    (tmp_path/'preview.json').write_text('{broken',encoding='utf-8')
    w._cad_finished(tmp_path,before,None,{'overall':'WARNING','artifacts':{}})
    assert w._cad_worker is None and w.get_parameters()==before
    assert 'CAD preview could not be displayed' in w.messages.toPlainText()


@pytest.mark.parametrize('reason',[{'cancelled':True},{'failed_phase':'preparation'}])
def test_cancel_or_numeric_failure_never_publishes_to_existing_case(window,tmp_path,monkeypatch,reason):
    from blade_designer.gui import main_window
    from blade_designer.cad import client
    class FakeWorker(QObject):
        progress=Signal(str);completed=Signal(object)
        def __init__(self,job,parent):super().__init__(parent);self.job=job
        def start(self):pass
        def cancel(self):pass
    monkeypatch.setattr(main_window,'CadExportWorker',FakeWorker)
    def unexpected(*args,**kwargs):raise AssertionError('Cancelled/failed preparation reached publication')
    monkeypatch.setattr(client,'publish_job',unexpected)
    case=tmp_path/'case';case.mkdir();(case/'existing.step').write_bytes(b'keep existing verified bytes')
    w=window;w.cad_editor.scope.setCurrentIndex(w.cad_editor.scope.findData('blade_only'))
    before=deepcopy(w.get_parameters());w.start_cad_job('mechanical',case)
    worker=w._cad_worker
    worker.completed.emit({'overall':'FAIL','artifacts':{},'error':{'message':'cancel/preparation failure'},**reason})
    assert w._cad_worker is None and w.get_parameters()==before
    assert sorted(path.name for path in case.iterdir())==['existing.step']
    assert (case/'existing.step').read_bytes()==b'keep existing verified bytes'


def test_close_waits_asynchronously_for_owned_worker_completion(window):
    from PySide6.QtCore import QTimer
    import time
    class PendingWorker(QObject):
        completed=Signal(object)
        def __init__(self,parent):super().__init__(parent);self.cancel_calls=0
        def cancel(self):
            self.cancel_calls+=1
            QTimer.singleShot(50,lambda:self.completed.emit({'overall':'FAIL','cancelled':True,'artifacts':{}}))
    w=window;worker=PendingWorker(w);w._cad_worker=worker
    app=QApplication.instance();ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(True));timer.start(10)
    try:
        w.close();assert w.isVisible() and w._cad_worker is worker
        deadline=time.monotonic()+3
        while w.isVisible() and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        assert not w.isVisible() and w._cad_worker is None and worker.cancel_calls==1
        assert ticks
    finally:timer.stop()
