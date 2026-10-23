"""Asynchronous numeric preparation, CAD execution and owned-process cancellation."""
import json,os,sys
from PySide6.QtCore import QObject,QProcess,QTimer,Signal
from ..cad.client import backend_python,ROOT,json_text,verified_snapshot_text


PREPARATION_TIMEOUT_MS=20*60*1000
CAD_TIMEOUT_MS=60*60*1000


class CadExportWorker(QObject):
    progress=Signal(str)
    completed=Signal(object)

    def __init__(self,job,parent=None):
        super().__init__(parent);self.job=job;self.buffer='';self.cancelled=False
        self.process=QProcess(self);self.process.setWorkingDirectory(str(ROOT))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.started.connect(self._process_started)
        self.process.errorOccurred.connect(self._process_error)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.cancel)
        self.log=[];self._completed=False;self._started=False;self._phase=None
        self.killer=None;self.termination_status='NOT_REQUESTED'

    def start(self):
        if self._started or self._completed:return
        self._started=True;self.timer.start(PREPARATION_TIMEOUT_MS)
        try:
            request=json.loads((self.job/'request.json').read_text(encoding='utf-8'))
            if not isinstance(request,dict):raise ValueError('Invalid CAD request structure.')
            if request.get('preparation_pending') is True:
                self._launch(sys.executable,'blade_designer.cad.pending_job','preparation')
            else:self._start_cad()
        except (ValueError,OSError) as exc:self._fail(str(exc),'CadExportError')

    def _start_cad(self):
        try:python=backend_python()
        except Exception as exc:self._fail(str(exc));return
        # The real default full-wheel case needs over 20 minutes. Preparation
        # time must not consume the separate, bounded CAD-kernel budget.
        self.timer.start(CAD_TIMEOUT_MS)
        self._launch(python,'blade_designer.cad.worker','cad')

    def _launch(self,python,module,phase):
        self._phase=phase;self.buffer=''
        self.process.start(str(python),['-X','utf8','-m',module,str(self.job.resolve())])

    def _process_started(self):
        if self.cancelled:self.cancel()

    def _process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            if self.cancelled:self._cancel_finished();return
            self._fail(self.process.errorString(),'CadExportError' if self._phase=='preparation' else 'BackendUnavailableError')

    def _read(self):
        text=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace')
        self.log.append(text);self.buffer+=text
        while '\n' in self.buffer:
            line,self.buffer=self.buffer.split('\n',1)
            if line.startswith('BLADE_CAD:'):
                try:
                    message=json.loads(line[10:])
                    if isinstance(message,dict) and isinstance(message.get('stage'),str):self.progress.emit(message['stage'])
                except ValueError:pass

    def cancel(self):
        if self._completed:return
        self.cancelled=True;self.timer.stop()
        if self.killer is not None and self.killer.state()!=QProcess.ProcessState.NotRunning:return
        if self.process.state()==QProcess.ProcessState.NotRunning:
            self._cancel_finished();return
        self.progress.emit('CANCELLING OWNED PROCESS TREE')
        if sys.platform=='win32' and self.process.processId():
            if self.killer is not None:self.killer.deleteLater()
            self.killer=QProcess(self)
            self.killer.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self.killer.finished.connect(self._kill_finished)
            self.killer.errorOccurred.connect(self._kill_error)
            executable=os.path.join(os.environ.get('SystemRoot',r'C:\Windows'),'System32','taskkill.exe')
            self.killer.start(executable,['/PID',str(self.process.processId()),'/T','/F'])
        else:
            self.termination_status='DIRECT_PROCESS_KILL_REQUESTED';self.process.kill()

    def _kill_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            self.termination_status='NOT_CONFIRMED'
            self.progress.emit('Cancellation helper failed; retry Cancel or wait for the owned worker to exit.')
            if self.process.state()==QProcess.ProcessState.NotRunning:self._cancel_finished()

    def _kill_finished(self,code,status):
        self.log.append(bytes(self.killer.readAllStandardOutput()).decode('utf-8',errors='replace'))
        self.termination_status=('PROCESS_TREE_STOPPED' if code==0 and status==QProcess.ExitStatus.NormalExit else 'NOT_CONFIRMED')
        if self.process.state()==QProcess.ProcessState.NotRunning:self._cancel_finished()
        elif self.termination_status=='NOT_CONFIRMED':
            # Do not kill only the venv launcher and abandon its child process.
            self.progress.emit('Process tree termination was not confirmed; retry Cancel or wait for worker exit.')

    def _cancel_finished(self):
        if self.killer is not None and self.killer.state()!=QProcess.ProcessState.NotRunning:return
        if self.process.state()!=QProcess.ProcessState.NotRunning:return
        self._fail('CAD calculation cancelled or timed out; no incomplete files published.','CadExportError')

    def _fail(self,message,category='BackendUnavailableError'):
        if self._completed:return
        self._completed=True;self.timer.stop()
        result={'overall':'FAIL','error':{'type':category,'message':message},'artifacts':{}}
        result['failed_phase']=self._phase
        if self.cancelled:result.update(cancelled=True,termination_status=self.termination_status)
        try:
            (self.job/'process.log').write_text(''.join(self.log),encoding='utf-8')
            (self.job/'result.json').write_text(json_text(result),encoding='utf-8')
        except OSError as exc:result['report_write_error']=str(exc)
        self.completed.emit(result)

    def _finished(self,code,status):
        if self._completed:return
        self._read()
        try:(self.job/'process.log').write_text(''.join(self.log),encoding='utf-8')
        except OSError:pass
        if self.cancelled:self._cancel_finished();return
        if code!=0 or status!=QProcess.ExitStatus.NormalExit:
            message='CAD process stopped unsuccessfully; no files published.'
            path=self.job/'result.json'
            if path.is_file():
                try:message=json.loads(path.read_text(encoding='utf-8')).get('error',{}).get('message',message)
                except (ValueError,OSError,AttributeError):pass
            self._fail(message,'CadExportError');return
        if self._phase=='preparation':
            try:
                request=json.loads((self.job/'request.json').read_text(encoding='utf-8'))
                if not isinstance(request,dict):raise ValueError('Invalid numeric CAD request structure.')
                if request.get('preparation_pending') is not False or not (self.job/'geometry.npz').is_file():
                    raise ValueError('Numeric CAD preparation is incomplete.')
                verified_snapshot_text(self.job,request['parameter_snapshot_hash'])
            except (ValueError,OSError,KeyError) as exc:self._fail(str(exc),'CadExportError');return
            self._start_cad();return
        self.timer.stop();path=self.job/'result.json'
        if path.is_file():
            try:
                result=json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(result,dict) or result.get('overall') not in ('PASS','WARNING','FAIL') or not isinstance(result.get('artifacts'),dict):
                    raise ValueError('Invalid result structure.')
            except (ValueError,OSError) as exc:self._fail('Invalid CAD validation report: '+str(exc),'CadExportError');return
            self._completed=True;self.completed.emit(result)
        else:self._fail('CAD process stopped without a validation report; no files published.','CadExportError')
