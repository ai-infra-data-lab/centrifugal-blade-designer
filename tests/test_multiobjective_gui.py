from copy import deepcopy
import pytest
from PySide6.QtWidgets import QFileDialog

from test_coordinate_study_gui import window, open_dialog, slow_start
from test_cad_async_worker import app, wait
from test_coordinate_proposal_io import source_study
from test_coordinate_proposal_gui import open_evaluated
from test_multiobjective import OBJECTIVES
from blade_designer.fileio.coordinate_study import pareto_results


def configure(dialog):
    dialog.second_objective.setText('pressure')
    dialog.second_direction.setCurrentIndex(1)
    dialog.multiobjective.setChecked(True)
    dialog.refresh_cases()
    dialog.results_tabs.setCurrentIndex(1)


def test_real_multiobjective_worker_resume_and_separate_predictions(window,app,source_study,tmp_path,monkeypatch):
    before=deepcopy(window.get_parameters());dialog=open_dialog(window)
    open_evaluated(dialog,source_study,monkeypatch);configure(dialog)
    ranked,fronts=pareto_results(dialog.results,OBJECTIVES)
    assert dialog.cases_table.columnCount()==7
    assert dialog.cases_table.item(0,0).text()==ranked[0]
    assert dialog.cases_table.item(0,6).text()==str(fronts[ranked[0]])
    assert dialog.pareto_plot.isVisible()
    assert len(dialog.pareto_plot.listDataItems())==2
    target=tmp_path/'next';dialog.count.setValue(3)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    dialog.proposal_button.click()
    assert dialog.worker is not None and not dialog.multiobjective.isEnabled()
    wait(app,lambda:dialog.worker is None)
    assert dialog.manifest['proposal']['objectives']==OBJECTIVES,dialog.status.text()
    assert not dialog.results
    assert all(dialog.cases_table.item(i,3).text()=='' and dialog.cases_table.item(i,5).text()==''
               and dialog.cases_table.item(i,6).text()=='' for i in range(4))
    assert 'pressure=' in dialog.cases_table.item(1,4).text()
    assert len(dialog.pareto_plot.listDataItems())==3
    dialog.results_tabs.setCurrentIndex(0)
    assert window.get_parameters()==before
    dialog.multiobjective.setChecked(False)
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a,**k:str(target))
    dialog.open_run()
    assert dialog.multiobjective.isChecked() and dialog.objectives()==OBJECTIVES
    assert dialog.second_direction.currentIndex()==1
    dialog.multiobjective.setChecked(False)
    assert dialog.cases_table.columnCount()==5 and not dialog.results_tabs.isTabVisible(1)


def test_duplicate_objectives_refused_and_stale_plot_removed(window,source_study,monkeypatch):
    dialog=open_dialog(window);open_evaluated(dialog,source_study,monkeypatch);configure(dialog)
    dialog.second_objective.setText('quality');dialog.refresh_cases()
    assert not dialog.pareto_plot.isVisible() and 'distinct' in dialog.status.text()
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:pytest.fail('Reject before destination'))
    dialog.proposal_button.click()
    assert dialog.worker is None and 'distinct' in dialog.status.text()


@pytest.mark.parametrize('action',['cancel','close'])
def test_multiobjective_cancel_close_protect_existing_source(window,app,source_study,tmp_path,monkeypatch,action):
    dialog=open_dialog(window);open_evaluated(dialog,source_study,monkeypatch);configure(dialog)
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
