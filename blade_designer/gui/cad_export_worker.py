"""QProcess keeps OCCT objects and computation outside the GUI process."""
import json,subprocess,sys
from PySide6.QtCore import QObject,QProcess,QTimer,Signal
from ..cad.client import backend_python,ROOT,json_text

class CadExportWorker(QObject):
    progress=Signal(str)
    completed=Signal(object)

    def __init__(self,job,parent=None):
        super().__init__(parent);self.job=job;self.buffer="";self.cancelled=False
        self.process=QProcess(self);self.process.setWorkingDirectory(str(ROOT))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.cancel)
        self.log=[];self._completed=False

    def start(self):
        try:python=backend_python()
        except Exception as exc:self._fail(str(exc));return
        self.process.errorOccurred.connect(lambda error:self._fail(self.process.errorString()) if error==QProcess.ProcessError.FailedToStart else None)
        self.process.start(str(python),["-X","utf8","-m","blade_designer.cad.worker",str(self.job.resolve())])
        self.timer.start(1200000)

    def _read(self):
        text=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace');self.log.append(text);self.buffer+=text
        while "\n" in self.buffer:
            line,self.buffer=self.buffer.split("\n",1)
            if line.startswith("BLADE_CAD:"):
                try:
                    message=json.loads(line[10:])
                    if "stage" in message:self.progress.emit(message["stage"])
                except ValueError:pass

    def cancel(self):
        self.cancelled=True
        if sys.platform=="win32" and self.process.processId():
            subprocess.run(["taskkill","/PID",str(self.process.processId()),"/T","/F"],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        else:self.process.kill()

    def _fail(self,message,category="BackendUnavailableError"):
        if self._completed:return
        self._completed=True
        self.timer.stop();result={"overall":"FAIL","error":{"type":category,"message":message},"artifacts":{}}
        (self.job/"result.json").write_text(json_text(result),encoding="utf-8");self.completed.emit(result)

    def _finished(self,*args):
        if self._completed:return
        self.timer.stop();self._read();(self.job/"process.log").write_text("".join(self.log),encoding="utf-8")
        path=self.job/"result.json"
        if self.cancelled:self._fail("CAD calculation cancelled or timed out; no incomplete files published.","CadExportError")
        elif path.is_file():
            try:result=json.loads(path.read_text(encoding="utf-8"))
            except (ValueError,OSError) as exc:self._fail("Invalid CAD validation report: "+str(exc),"CadExportError");return
            self._completed=True;self.completed.emit(result)
        else:self._fail("CAD process stopped without a validation report; no files published.","CadExportError")
