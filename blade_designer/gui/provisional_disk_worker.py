"""Reuse owned-tree cancellation for the Qt-free disk preparation process."""
import json,sys
from PySide6.QtCore import QProcess
from .cad_export_worker import CadExportWorker


class ProvisionalDiskWorker(CadExportWorker):
    def start(self):
        if self._started or self._completed:return
        self._started=True;self.timer.start(1200000)
        self._launch(sys.executable,'blade_designer.cad.provisional_disk_job','provisional_disk')

    def _process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            if self.cancelled:self._cancel_finished();return
            self._fail('Provisional disk Python process could not start: '+self.process.errorString(),'CadExportError')

    def _finished(self,code,status):
        if self._completed:return
        self._read()
        try:(self.job/'process.log').write_text(''.join(self.log),encoding='utf-8')
        except OSError:pass
        if self.cancelled:self._cancel_finished();return
        if code!=0 or status!=QProcess.ExitStatus.NormalExit:
            self._fail('Provisional disk calculation stopped; no CAD export started.','CadExportError');return
        try:
            result=json.loads((self.job/'result.json').read_text(encoding='utf-8'))
            if not isinstance(result,dict) or result.get('overall')!='PASS' or result.get('phase')!='PROVISIONAL_DISK_READY':
                raise ValueError('Incomplete provisional disk result.')
        except (OSError,ValueError) as exc:self._fail(str(exc),'CadExportError');return
        self.timer.stop();self._completed=True;self.completed.emit(result)
