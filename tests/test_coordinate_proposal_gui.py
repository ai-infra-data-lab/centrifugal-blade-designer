from copy import deepcopy
import json
from pathlib import Path
import pytest
from PySide6.QtWidgets import QFileDialog

from test_coordinate_study_gui import window, open_dialog, slow_start
from test_cad_async_worker import app, wait
from test_coordinate_proposal_io import source_study
from blade_designer.fileio.coordinate_study import digest


def open_evaluated(dialog,source_study,monkeypatch):
    spec=source_study[-1]
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a,**k:spec['source_directory'])
    dialog.open_run()
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(spec['results_path'],''))
    dialog.objective.setText('quality');dialog.import_csv()
    assert dialog.results and dialog.results_hash==spec['results_hash']


def test_real_proposal_worker_predictions_never_become_external_scores(window,app,source_study,tmp_path,monkeypatch):
    before=deepcopy(window.get_parameters());dialog=open_dialog(window)
    open_evaluated(dialog,source_study,monkeypatch)
    assert '独立1変数' in dialog.proposal_note.text() and '8点' in dialog.proposal_note.text()
    target=tmp_path/'next';dialog.count.setValue(3)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    dialog.proposal_button.click()
    assert dialog.worker is not None and not dialog.proposal_button.isEnabled()
    wait(app,lambda:dialog.worker is None)
    assert dialog.manifest['sampling']=='rbf_external',dialog.status.text()
    assert not dialog.results and dialog.results_path is None
    assert 'quality' in dialog.cases_table.horizontalHeaderItem(4).text()
    assert all(dialog.cases_table.item(i,3).text()=='' for i in range(dialog.cases_table.rowCount()))
    assert any(dialog.cases_table.item(i,4).text() for i in range(dialog.cases_table.rowCount()))
    assert window.get_parameters()==before
    assert dialog.proposal_button.isEnabled()


def test_proposal_without_evaluations_is_refused_before_folder_dialog(window,monkeypatch):
    dialog=open_dialog(window)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:pytest.fail('No destination before evaluated source'))
    dialog.proposal_button.click()
    assert dialog.worker is None and '外部評価CSV' in dialog.status.text()


@pytest.mark.parametrize('action',['cancel','close'])
def test_proposal_uses_owned_process_cancel_and_close(window,app,source_study,tmp_path,monkeypatch,action):
    dialog=open_dialog(window);open_evaluated(dialog,source_study,monkeypatch)
    slow_start(monkeypatch);target=tmp_path/'next';dialog.count.setValue(3)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    dialog.proposal_button.click();worker=dialog.worker;reports=[]
    worker.completed.connect(reports.append)
    wait(app,lambda:any('OWNED_COORDINATE_READY' in s for s in worker.log))
    if action=='cancel':dialog.cancel_button.click()
    else:dialog.close()
    wait(app,lambda:bool(reports))
    assert reports[0]['cancelled'] and reports[0]['termination_status']=='PROCESS_TREE_STOPPED'
    assert not target.exists()


def test_import_failure_preserves_results_and_frozen_source_identity(window,source_study,tmp_path,monkeypatch):
    dialog=open_dialog(window);open_evaluated(dialog,source_study,monkeypatch)
    before=deepcopy(dialog.results);path_before=dialog.results_path;hash_before=dialog.results_hash
    path=tmp_path/'invalid.csv';path.write_text('invalid')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    dialog.import_csv()
    assert dialog.results==before and dialog.results_path==path_before and dialog.results_hash==hash_before
    assert digest(path_before.read_bytes())==hash_before


def test_capture_discards_training_source_but_does_not_modify_design(window,source_study,monkeypatch):
    dialog=open_dialog(window);open_evaluated(dialog,source_study,monkeypatch)
    before=deepcopy(window.get_parameters());dialog.capture()
    assert dialog.manifest is None and not dialog.results and dialog.source_directory is None
    assert dialog.results_path is None and dialog.results_hash is None
    assert window.get_parameters()==before
