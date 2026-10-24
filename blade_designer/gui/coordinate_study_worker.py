"""Reuse the owned-process cancellation contract for coordinate-only batches."""
import json
import sys
from PySide6.QtCore import QProcess
from .cad_export_worker import CadExportWorker, PREPARATION_TIMEOUT_MS


class CoordinateStudyWorker(CadExportWorker):
    def start(self):
        if self._started or self._completed:
            return
        self._started = True
        self.timer.start(PREPARATION_TIMEOUT_MS)
        self._launch(sys.executable, 'blade_designer.fileio.coordinate_study', 'coordinates')

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            if self.cancelled:
                self._cancel_finished()
            else:
                self._fail(self.process.errorString(), 'CoordinateStudyError')

    def _cancel_finished(self):
        if self.killer is not None and self.killer.state() != QProcess.ProcessState.NotRunning:
            return
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self._fail('座標出力を取消しました。公開が完了済みの場合は完成したStudyが残ります。'
                   '再利用する場合は「保存済みStudyを開く」で検証してください。', 'CoordinateStudyError')

    def _finished(self, code, status):
        if self._completed:
            return
        self._read()
        try:
            (self.job / 'process.log').write_text(''.join(self.log), encoding='utf-8')
        except OSError:
            pass
        if self.cancelled:
            self._cancel_finished()
            return
        try:
            report = json.loads((self.job / 'result.json').read_text(encoding='utf-8'))
            request = json.loads((self.job / 'request.json').read_text(encoding='utf-8'))
            if not isinstance(report, dict) or not isinstance(request, dict):
                raise ValueError('Malformed coordinate-study request or result.')
            if code != 0 or status != QProcess.ExitStatus.NormalExit or report.get('overall') != 'PASS':
                raise ValueError(report.get('error', {}).get('message', 'Coordinate study failed.'))
            if (report.get('phase') != 'COORDINATE_STUDY_READY'
                    or report.get('snapshot_hash') != request['snapshot_hash']
                    or report.get('run_id') != request['run_id']
                    or report.get('directory') != request['output']):
                raise ValueError('Coordinate-study result does not match its request.')
        except (OSError, ValueError, KeyError, AttributeError) as exc:
            self._fail(str(exc), 'CoordinateStudyError')
            return
        self._completed = True
        self.timer.stop()
        self.completed.emit(report)
