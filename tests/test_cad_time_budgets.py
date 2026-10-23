
"""Qt lifecycle budget policy; simulated stage transitions are not CAD proof."""
from pathlib import Path
import sys,json
import pytest
from PySide6.QtCore import QProcess
from blade_designer.gui import cad_export_worker as module
from blade_designer.gui.preview_worker import PreviewWorker
from blade_designer.gui.provisional_disk_worker import ProvisionalDiskWorker
from test_cad_async_worker import app


def held_worker(tmp_path,monkeypatch,pending=False,worker_class=module.CadExportWorker):
    job=tmp_path/'lifecycle-only';job.mkdir();(job/'request.json').write_text(json.dumps({'preparation_pending':pending}),encoding='utf-8')
    worker=worker_class(job);stages=[];reports=[]
    def launch(python,name,phase):worker._phase=phase;stages.append(phase)
    monkeypatch.setattr(module,'backend_python',lambda:Path(sys.executable))
    monkeypatch.setattr(worker,'_launch',launch);monkeypatch.setattr(worker,'_read',lambda:None)
    worker.completed.connect(reports.append)
    return worker,stages,reports


def test_direct_cad_receives_full_kernel_budget_and_manual_cancel_still_finishes(app,tmp_path,monkeypatch):
    worker,stages,reports=held_worker(tmp_path,monkeypatch)
    try:
        worker.start();assert stages==['cad'] and worker.timer.isActive()
        assert worker.timer.interval()==60*60*1000 and worker.timer.remainingTime()>59*60*1000
        worker.cancel();assert not worker.timer.isActive() and len(reports)==1
        assert reports[0]['cancelled'] and reports[0]['overall']=='FAIL' and reports[0]['artifacts']=={}
    finally:worker.cancel();worker.deleteLater();app.processEvents()


def test_completed_preparation_does_not_spend_the_kernel_budget(app,tmp_path,monkeypatch):
    worker,stages,reports=held_worker(tmp_path,monkeypatch,True)
    try:
        worker.start();assert worker.timer.interval()==20*60*1000 and stages==['preparation']
        # Simulate a nearly expired preparation budget, not a real geometry result.
        worker.timer.start(1)
        (worker.job/'request.json').write_text(json.dumps({'preparation_pending':False,'parameter_snapshot_hash':'LIFECYCLE_ONLY'}),encoding='utf-8')
        (worker.job/'geometry.npz').write_bytes(b'LIFECYCLE_ONLY')
        monkeypatch.setattr(module,'verified_snapshot_text',lambda *args:'LIFECYCLE_ONLY')
        worker._finished(0,QProcess.ExitStatus.NormalExit)
        app.processEvents()
        assert stages==['preparation','cad'] and not reports and worker.timer.isActive()
        assert worker.timer.interval()==60*60*1000 and worker.timer.remainingTime()>59*60*1000
    finally:worker.cancel();worker.deleteLater();app.processEvents()


def test_incomplete_preparation_never_starts_kernel_or_rearms_deadline(app,tmp_path,monkeypatch):
    worker,stages,reports=held_worker(tmp_path,monkeypatch,True)
    try:
        worker.start();worker._finished(0,QProcess.ExitStatus.NormalExit)
        assert stages==['preparation'] and not worker.timer.isActive()
        assert worker.timer.interval()==20*60*1000 and len(reports)==1
        assert reports[0]['overall']=='FAIL' and reports[0]['artifacts']=={}
    finally:worker.cancel();worker.deleteLater();app.processEvents()


def test_unavailable_backend_stops_preparation_deadline(app,tmp_path,monkeypatch):
    worker,stages,reports=held_worker(tmp_path,monkeypatch)
    def unavailable():raise OSError('backend unavailable')
    monkeypatch.setattr(module,'backend_python',unavailable)
    try:
        worker.start();assert not stages and not worker.timer.isActive()
        assert worker.timer.interval()==20*60*1000 and len(reports)==1
        assert reports[0]['error']['type']=='BackendUnavailableError'
    finally:worker.cancel();worker.deleteLater();app.processEvents()


@pytest.mark.parametrize('worker_class',[PreviewWorker,ProvisionalDiskWorker])
def test_normal_numerical_workers_keep_original_20_minute_limit(app,tmp_path,monkeypatch,worker_class):
    worker,stages,reports=held_worker(tmp_path,monkeypatch,worker_class=worker_class)
    try:
        worker.start();assert worker.timer.interval()==20*60*1000 and worker.timer.isActive()
        worker.cancel();assert not worker.timer.isActive() and len(reports)==1
    finally:worker.cancel();worker.deleteLater();app.processEvents()
