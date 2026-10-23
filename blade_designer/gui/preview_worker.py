"""Owned numerical process and one-running/latest-pending preview controller."""
from copy import deepcopy
from dataclasses import dataclass
import json
import sys

from PySide6.QtCore import QObject, QProcess, Signal

from .cad_export_worker import CadExportWorker
from ..fileio.preview_job import ROOT, queue_preview, read_preview
from ..fileio.preview_retention import PreviewJobRetention


class PreviewWorker(CadExportWorker):
    def start(self):
        if self._started or self._completed:return
        self._started=True;self.timer.start(1200000)
        self._launch(sys.executable,"blade_designer.fileio.preview_job","preview")

    def _process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            if self.cancelled:self._cancel_finished();return
            self._fail("Preview process could not start: "+self.process.errorString(),"PreviewError")

    def _cancel_finished(self):
        if self.killer is not None and self.killer.state()!=QProcess.ProcessState.NotRunning:return
        if self.process.state()!=QProcess.ProcessState.NotRunning:return
        self._fail("Preview cancelled or timed out; no result applied.","PreviewError")

    def _finished(self,code,status):
        if self._completed:return
        self._read()
        try:(self.job/"process.log").write_text("".join(self.log),encoding="utf-8")
        except OSError:pass
        if self.cancelled:self._cancel_finished();return
        try:
            report=json.loads((self.job/"result.json").read_text(encoding="utf-8"))
            if code!=0 or status!=QProcess.ExitStatus.NormalExit or not isinstance(report,dict):
                raise ValueError("Preview process failed.")
            if report.get("overall")!="PASS" or report.get("phase")!="PREVIEW_READY":
                raise ValueError("Incomplete preview result.")
        except (OSError,ValueError) as exc:self._fail(str(exc),"PreviewError");return
        self._completed=True;self.timer.stop();self.completed.emit(report)


@dataclass
class PreviewRequest:
    generation: int
    params: object
    kind: str
    include_rows: bool


class PreviewController(QObject):
    ready=Signal(object,object)
    failed=Signal(object,str)
    progress=Signal(str)
    idle=Signal()

    def __init__(self,parent=None,worker_factory=PreviewWorker,keep_jobs=False):
        super().__init__(parent)
        self.worker_factory=worker_factory;self.worker=None;self.pending=None;self.closing=False;self._disposing=False
        self.last_report=None
        self.retention=PreviewJobRetention(ROOT/'artifacts'/'preview-runs',keep_jobs=keep_jobs)

    def _retention_warning(self,previous):
        if tuple(self.retention.warnings)!=previous and self.retention.warnings:
            self.progress.emit('Preview temporary-file cleanup: '+self.retention.warnings[-1])

    def _retire_job(self,job,report):
        previous=tuple(self.retention.warnings)
        self.retention.finished(job,report)
        if self._disposing:self.retention.trim(dispose=True)
        self._retention_warning(previous)

    @property
    def busy(self):return self.worker is not None

    def submit(self,request):
        if self.closing:return
        request=deepcopy(request)
        if self.worker is not None:
            self.pending=request;self.worker.cancel()
        else:self._start(request)

    def invalidate(self):
        self.pending=None
        if self.worker is not None:self.worker.cancel()

    def shutdown(self):
        self.closing=True;self.invalidate()

    def dispose(self,*args):
        self._disposing=True
        self.shutdown()
        previous=tuple(self.retention.warnings);self.retention.trim(dispose=True);self._retention_warning(previous)
        if self.worker is None:self.deleteLater()

    def _start(self,request):
        job=None
        try:
            job=queue_preview(request.params,request.kind,request.include_rows)
            try:self.retention.register(job)
            except (OSError,ValueError) as exc:
                self.progress.emit('Preview temporary files preserved: '+str(exc))
            worker=self.worker_factory(job,self)
        except (OSError,ValueError,ArithmeticError) as exc:
            if job is not None:self._retire_job(job,{'overall':'FAIL'})
            self.failed.emit(request,str(exc));self.idle.emit();return
        self.worker=worker
        worker.completed.connect(lambda report:self._finished(worker,job,request,report))
        if hasattr(worker,'progress'):worker.progress.connect(self.progress.emit)
        worker.start()

    def _finished(self,worker,job,request,report):
        if worker is not self.worker:return
        self.last_report=report
        self.worker=None
        pending=self.pending;self.pending=None
        if not self.closing and pending is None:
            try:
                if worker.cancelled:raise ValueError(report.get('error',{}).get('message','Preview cancelled or timed out.'))
                if report.get("overall")!="PASS":raise ValueError(report.get("error",{}).get("message","Preview failed."))
                result=read_preview(job,request.params,request.kind,request.include_rows)
            except (OSError,ValueError,ArithmeticError,TypeError,KeyError,RecursionError) as exc:
                self.failed.emit(request,str(exc))
            else:self.ready.emit(request,result)
        self._retire_job(job,report)
        worker.deleteLater()
        # ready/failed callbacks may have queued a newer request or closed us.
        if pending is not None and not self.closing and self.worker is None:self._start(pending)
        if self.worker is None:self.idle.emit()
        if self._disposing:self.deleteLater()
