"""Actual child processes and Qt lifecycle; mock CAD results are labeled as such."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import ctypes,json,re,sys,time
from pathlib import Path
import pytest
from PySide6.QtCore import QProcess,QTimer
from PySide6.QtWidgets import QApplication
from blade_designer.gui import cad_export_worker as module
from blade_designer.cad.pending_job import queue_job
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.cad import MechanicalExportScope


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def wait(app,predicate,timeout=60):
    deadline=time.monotonic()+timeout
    while not predicate() and time.monotonic()<deadline:
        app.processEvents();time.sleep(.005)
    assert predicate(),'Qt worker did not finish within the bounded test time'


def script_worker(tmp_path,monkeypatch,code):
    job=tmp_path/'job';job.mkdir();(job/'request.json').write_text('{}',encoding='utf-8')
    worker=module.CadExportWorker(job)
    monkeypatch.setattr(module,'backend_python',lambda:Path(sys.executable))
    original=worker.process.start
    worker.process.start=lambda *args:original(sys.executable,['-X','utf8','-c',code])
    return worker


def test_actual_numeric_child_finishes_before_mock_cad_stage(app,tmp_path):
    params=BladeParameters();params.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    job=queue_job(params,job_directory=tmp_path/'job')
    worker=module.CadExportWorker(job);reports=[];cad=[]
    def simulated_cad():
        cad.append(json.loads((job/'request.json').read_text(encoding='utf-8')))
        worker.timer.stop();worker._completed=True
        worker.completed.emit({'overall':'WARNING','artifacts':{},'simulation':'LIFECYCLE_ONLY'})
    worker._start_cad=simulated_cad;worker.completed.connect(reports.append)
    try:
        worker.start();wait(app,lambda:bool(reports))
        assert len(cad)==len(reports)==1 and cad[0]['preparation_pending'] is False
        assert (job/'geometry.npz').is_file() and worker.process.state()==QProcess.ProcessState.NotRunning
        assert reports[0]['simulation']=='LIFECYCLE_ONLY'
    finally:
        if not worker._completed:worker.cancel();wait(app,lambda:worker._completed)
        worker.deleteLater();app.processEvents()


def test_invalid_numeric_input_never_starts_cad(app,tmp_path):
    params=BladeParameters();job=queue_job(params,job_directory=tmp_path/'job')
    (job/'geometry_snapshot.json').write_text('{}',encoding='utf-8')
    worker=module.CadExportWorker(job);reports=[];cad=[]
    worker._start_cad=lambda:cad.append(True);worker.completed.connect(reports.append)
    worker.start();wait(app,lambda:bool(reports))
    assert not cad and reports[0]['overall']=='FAIL' and reports[0]['failed_phase']=='preparation'
    assert reports[0]['artifacts']=={} and not (job/'geometry.npz').exists()
    worker.deleteLater();app.processEvents()


@pytest.mark.parametrize('content',[None,'[]','{}','{"overall":"PASS","artifacts":[]}'])
def test_missing_or_malformed_report_is_not_adopted(app,tmp_path,monkeypatch,content):
    path=repr(str(tmp_path/'job'/'result.json'))
    code='pass' if content is None else f'from pathlib import Path;Path({path}).write_text({content!r},encoding="utf-8")'
    worker=script_worker(tmp_path,monkeypatch,code);reports=[];worker.completed.connect(reports.append)
    worker.start();wait(app,lambda:bool(reports))
    assert len(reports)==1 and reports[0]['overall']=='FAIL' and reports[0]['artifacts']=={}
    worker.deleteLater();app.processEvents()


def test_nonzero_process_exit_cannot_reuse_a_success_report(app,tmp_path,monkeypatch):
    path=repr(str(tmp_path/'job'/'result.json'))
    code=f'from pathlib import Path;Path({path}).write_text(\'{{"overall":"PASS","artifacts":{{}}}}\',encoding="utf-8");raise SystemExit(7)'
    worker=script_worker(tmp_path,monkeypatch,code);reports=[];worker.completed.connect(reports.append)
    worker.start();wait(app,lambda:bool(reports))
    assert len(reports)==1 and reports[0]['overall']=='FAIL' and reports[0]['artifacts']=={}
    worker.deleteLater();app.processEvents()


def test_missing_executable_emits_one_failure(app,tmp_path,monkeypatch):
    job=tmp_path/'job';job.mkdir();(job/'request.json').write_text('{}',encoding='utf-8')
    monkeypatch.setattr(module,'backend_python',lambda:tmp_path/'missing-python.exe')
    worker=module.CadExportWorker(job);reports=[];worker.completed.connect(reports.append)
    worker.start();wait(app,lambda:bool(reports));worker.cancel();app.processEvents()
    assert len(reports)==1 and reports[0]['overall']=='FAIL' and not worker.timer.isActive()
    worker.deleteLater();app.processEvents()


class DelayedTreeKiller(QProcess):
    """Keep the real owned-tree kill pending long enough to test GUI delivery."""
    def start(self,program,args):
        if Path(program).name.lower()=='taskkill.exe':
            code='import subprocess,sys,time;time.sleep(.3);raise SystemExit(subprocess.run(sys.argv[1:],creationflags=subprocess.CREATE_NO_WINDOW).returncode)'
            return super().start(sys.executable,['-c',code,program,*args])
        return super().start(program,args)


@pytest.mark.skipif(sys.platform!='win32',reason='Windows owned venv launcher/tree cancellation')
def test_cancel_delivers_events_and_waits_for_real_child_tree(app,tmp_path,monkeypatch):
    monkeypatch.setattr(module,'QProcess',DelayedTreeKiller)
    code="import subprocess,sys,time;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)']);print('OWNED_CHILD:'+str(p.pid),flush=True);time.sleep(120)"
    worker=script_worker(tmp_path,monkeypatch,code);reports=[];ticks=[]
    worker.completed.connect(reports.append);heartbeat=QTimer();heartbeat.timeout.connect(lambda:ticks.append(time.monotonic()));heartbeat.start(10)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32];kernel.WaitForSingleObject.restype=ctypes.c_uint32
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=None
    try:
        worker.start();wait(app,lambda:bool(re.search(r'OWNED_CHILD:(\d+)',''.join(worker.log))))
        pid=int(re.search(r'OWNED_CHILD:(\d+)',''.join(worker.log)).group(1))
        handle=kernel.OpenProcess(0x100000,False,pid);assert handle
        worker.cancel();after_cancel=len(ticks);wait(app,lambda:bool(reports))
        assert len(ticks)-after_cancel>=2
        assert reports[0]['cancelled']
        assert reports[0]['termination_status'] in ('PROCESS_TREE_STOPPED','NOT_CONFIRMED')
        assert reports[0]['overall']=='FAIL' and reports[0]['artifacts']=={}
        assert worker.process.state()==worker.killer.state()==QProcess.ProcessState.NotRunning
        assert kernel.WaitForSingleObject(handle,0)==0,(''.join(worker.log),worker.killer.errorString(),worker.killer.exitCode())
        worker.cancel();app.processEvents();assert len(reports)==1
    finally:
        heartbeat.stop()
        if not worker._completed:worker.cancel();wait(app,lambda:worker._completed)
        if handle:kernel.CloseHandle(handle)
        worker.deleteLater();app.processEvents()


def test_cancel_during_process_start_does_not_start_another_phase(app,tmp_path,monkeypatch):
    worker=script_worker(tmp_path,monkeypatch,'import time;time.sleep(120)')
    reports=[];worker.completed.connect(reports.append)
    worker.start();worker.cancel();wait(app,lambda:bool(reports))
    assert len(reports)==1 and reports[0]['cancelled'] and reports[0]['artifacts']=={}
    assert worker.process.state()==QProcess.ProcessState.NotRunning
    assert worker.killer is None or worker.killer.state()==QProcess.ProcessState.NotRunning
    worker.deleteLater();app.processEvents()
