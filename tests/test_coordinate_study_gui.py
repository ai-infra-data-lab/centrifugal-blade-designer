import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
import json
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QFileDialog, QDialog
from shiboken6 import isValid, delete

from test_cad_async_worker import app, wait
from blade_designer.gui.main_window import MainWindow
from blade_designer.gui.coordinate_study_worker import CoordinateStudyWorker
from blade_designer.fileio.coordinate_study import project_hash, read_study
from blade_designer.optimization.coordinate_parameters import _key
from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.blade_rows import initial_rows


@pytest.fixture
def window(app):
    project = BladeParameters()
    project.blade_rows = initial_rows(project)
    project.active_blade_row = project.blade_rows[0].identifier
    window = MainWindow(default_parameters=project)
    window.show()
    app.processEvents()
    yield window
    if isValid(window):
        window.close()
        wait(app, lambda: not isValid(window) or not window.isVisible())
        if isValid(window):
            window.deleteLater()
    app.processEvents()


def open_dialog(window):
    window.open_coordinate_study()
    return window._tool_dialogs['coordinate_study']


def test_menu_capture_and_multiple_row_apply_undo_redo(window, app):
    before = deepcopy(window.get_parameters())
    assert any('座標最適化' in a.text() for a in window.tools_menu.actions())
    dialog = open_dialog(window)
    assert dialog.study.baseline == before
    first, second = before.blade_rows
    values = {_key(first.identifier, 'main', 0, 'beta_te'): 1.,
              _key(second.identifier, 'main', 0, 'beta_te'): -2.}
    candidate = dialog.study.candidate(values)
    count = window.undo_stack.count()
    dialog.apply_design(candidate, project_hash(before))
    after = window.get_parameters()
    assert window.undo_stack.count() == count + 1
    assert after.blade_rows[0].parameters.sections[0].blade_angle.points[-1].value == 51
    assert after.blade_rows[1].parameters.diffuser_profile.blade_angle.points[-1].value == 48
    window.undo()
    assert window.get_parameters() == before
    window.redo()
    assert window.get_parameters() == after


def test_stale_baseline_cannot_overwrite_current_design(window):
    dialog = open_dialog(window)
    before = dialog.study.baseline
    window.reverse_rotation()
    current = deepcopy(window.get_parameters())
    with pytest.raises(ValueError, match='基準'):
        dialog.apply_design(dialog.study.candidate({}), project_hash(before))
    assert window.get_parameters() == current


def test_real_export_worker_and_resume_are_coordinate_only(window, app, tmp_path, monkeypatch):
    dialog = open_dialog(window)
    before = window.get_parameters()
    dialog.count.setValue(0)
    target = tmp_path / 'study'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    dialog.export()
    worker = dialog.worker
    assert worker is not None and not dialog.export_button.isEnabled()
    wait(app, lambda: dialog.worker is None)
    assert dialog.manifest is not None, dialog.status.text()
    assert dialog.manifest['cad'] == 'NOT_EVALUATED' and dialog.manifest['cfd'] == 'NOT_EXECUTED'
    assert window.get_parameters() == before
    assert len(dialog.manifest['cases']) == 1
    _, manifest = read_study(target)
    assert manifest == dialog.manifest
    assert not list(target.rglob('*.step'))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a, **k: str(target))
    dialog.open_run()
    assert dialog.study.baseline == before
    assert dialog.options.include_hub and dialog.options.include_shroud


def test_existing_directory_rejected_before_worker_start(window, tmp_path, monkeypatch):
    dialog = open_dialog(window)
    protected = tmp_path / 'marker.txt'
    protected.write_text('keep')
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(tmp_path), ''))
    dialog.export()
    assert dialog.worker is None and protected.read_text() == 'keep'
    assert '上書き' in dialog.status.text()


def test_coordinate_preferences_survive_settings_reopen(window, monkeypatch):
    dialog = open_dialog(window)
    expected = CoordinateCsvOptions(('z_mm', 'rtheta_mm', 'r_mm'), True, False, True, True, True,
                                    'separate', 'txt', 'drawing')
    dialog.options = expected
    monkeypatch.setattr(QDialog, 'exec', lambda self: QDialog.DialogCode.Accepted)
    dialog.settings()
    assert dialog.options == expected


def slow_start(monkeypatch):
    original = CoordinateStudyWorker.start
    def start(worker):
        real = worker.process.start
        worker.process.start = lambda *args: real(sys.executable, ['-u', '-c',
            "import time; print('OWNED_COORDINATE_READY',flush=True); time.sleep(60)"])
        original(worker)
    monkeypatch.setattr(CoordinateStudyWorker, 'start', start)


@pytest.mark.parametrize('action', ['cancel', 'dialog_close', 'parent_close', 'parent_delete', 'forced_dialog_delete'])
def test_owned_process_cancel_and_close_paths(window, app, tmp_path, monkeypatch, action):
    slow_start(monkeypatch)
    dialog = open_dialog(window)
    dialog.count.setValue(0)
    target = tmp_path / 'study'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    dialog.export()
    worker = dialog.worker
    reports = []
    worker.completed.connect(reports.append)
    wait(app, lambda: any('OWNED_COORDINATE_READY' in s for s in worker.log))
    if action == 'cancel':
        worker.cancel()
    elif action == 'dialog_close':
        dialog.close()
    elif action == 'parent_close':
        window.close()
    elif action == 'parent_delete':
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    else:
        delete(dialog)
    wait(app, lambda: bool(reports))
    assert reports[0]['cancelled'] and reports[0]['overall'] == 'FAIL'
    if sys.platform == 'win32':
        assert reports[0]['termination_status'] == 'PROCESS_TREE_STOPPED'
    assert not target.exists()
    if action == 'parent_delete':
        wait(app, lambda: not isValid(window))
    if action == 'parent_close':
        wait(app, lambda: not window.isVisible())
    if action == 'forced_dialog_delete':
        reopened = open_dialog(window)
        assert isValid(reopened) and reopened.isVisible()


def test_wrong_worker_result_does_not_get_adopted(app, tmp_path):
    job = tmp_path / 'job'
    job.mkdir()
    (job / 'request.json').write_text(json.dumps({'snapshot_hash': 'expected', 'run_id': 'expected',
                                               'output': str(tmp_path / 'output')}))
    (job / 'result.json').write_text(json.dumps({'overall': 'PASS', 'phase': 'COORDINATE_STUDY_READY',
                                               'snapshot_hash': 'wrong', 'run_id': 'expected'}))
    from PySide6.QtCore import QProcess
    worker = CoordinateStudyWorker(job)
    reports = []
    worker.completed.connect(reports.append)
    worker._finished(0, QProcess.ExitStatus.NormalExit)
    assert len(reports) == 1 and reports[0]['overall'] == 'FAIL'
    worker.deleteLater()
    app.processEvents()
