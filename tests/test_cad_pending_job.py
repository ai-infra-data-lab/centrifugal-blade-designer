"""Freeze first, prepare outside Qt, promote a complete numeric request last."""
from copy import deepcopy
from pathlib import Path
import json,shutil,subprocess,sys
import numpy as np
import pytest
from blade_designer.cad import pending_job as pending
from blade_designer.cad.client import ROOT,prepare_job,publish_job
from blade_designer.cad.errors import CadExportError
from blade_designer.fileio.project_io import load_project
from blade_designer.models.blade_rows import initial_rows,row_parameters
from blade_designer.models.cad import MechanicalExportScope
from blade_designer.models.parameters import BladeParameters


@pytest.fixture(scope='module')
def parameters():
    project=load_project(ROOT/'blade_designer/defaults/default_project.json')
    params=row_parameters(project,next(row for row in project.blade_rows if row.kind=='impeller'))
    params.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    return params


@pytest.fixture(scope='module')
def legacy_job(parameters,tmp_path_factory):
    return prepare_job(parameters,job_directory=tmp_path_factory.mktemp('legacy_numeric')/'job')


def copied_preparer(legacy_job):
    def prepare(project,action,directory):
        shutil.copytree(legacy_job,directory)
        return Path(directory)
    return prepare


def test_queue_freezes_input_without_generating_blades(parameters,tmp_path,monkeypatch):
    from blade_designer.cad import client
    def unexpected(*args,**kwargs):raise AssertionError('Blade generation ran on the caller thread')
    monkeypatch.setattr(client,'generate_impeller',unexpected)
    params=deepcopy(parameters)
    job=pending.queue_job(params,job_directory=tmp_path/'job')
    params.cad_export.fillet.hub_radius_mm=3.5
    request=json.loads((job/'request.json').read_text(encoding='utf-8'))
    snapshot=json.loads((job/'geometry_snapshot.json').read_text(encoding='utf-8'))
    assert request['preparation_pending'] is True and not (job/'geometry.npz').exists()
    assert snapshot['cad_export']['fillet']['hub_radius_mm']==parameters.cad_export.fillet.hub_radius_mm


def test_preparation_matches_synchronous_request_and_all_arrays(parameters,legacy_job,tmp_path):
    before=deepcopy(parameters)
    job=pending.queue_job(parameters,job_directory=tmp_path/'job')
    pending.finish_preparation(job)
    request=json.loads((job/'request.json').read_text(encoding='utf-8'))
    assert request.pop('preparation_pending') is False
    assert request==json.loads((legacy_job/'request.json').read_text(encoding='utf-8'))
    assert (job/'geometry_snapshot.json').read_bytes()==(legacy_job/'geometry_snapshot.json').read_bytes()
    with np.load(job/'geometry.npz',allow_pickle=False) as actual,np.load(legacy_job/'geometry.npz',allow_pickle=False) as expected:
        assert actual.files==expected.files
        for name in actual.files:np.testing.assert_array_equal(actual[name],expected[name])
    assert parameters==before


def test_modified_input_rejected_before_numeric_generation(parameters,tmp_path,monkeypatch):
    job=pending.queue_job(parameters,job_directory=tmp_path/'job')
    source=job/'geometry_snapshot.json';data=json.loads(source.read_text(encoding='utf-8'))
    data['geometry']['vane_count']+=1;source.write_text(json.dumps(data),encoding='utf-8')
    def unexpected(*args,**kwargs):raise AssertionError('Modified input reached the generator')
    monkeypatch.setattr(pending,'prepare_job',unexpected)
    with pytest.raises(ValueError,match='hash mismatch'):pending.finish_preparation(job)
    assert not (job/'geometry.npz').exists()


@pytest.mark.parametrize('changed_file',['geometry_snapshot.json','request.json'])
def test_changes_during_preparation_never_promote_ready_request(parameters,legacy_job,tmp_path,monkeypatch,changed_file):
    job=pending.queue_job(parameters,job_directory=tmp_path/'job')
    copy=copied_preparer(legacy_job)
    def mutate(project,action,directory):
        prepared=copy(project,action,directory)
        path=job/changed_file;path.write_text(path.read_text(encoding='utf-8')+' ',encoding='utf-8')
        return prepared
    monkeypatch.setattr(pending,'prepare_job',mutate)
    with pytest.raises(ValueError,match='changed during'):pending.finish_preparation(job)
    assert not (job/'geometry.npz').exists()
    assert json.loads((job/'request.json').read_text(encoding='utf-8'))['preparation_pending'] is True


@pytest.mark.parametrize('failure_at',[1,2])
def test_failed_promotion_cannot_mark_partial_numeric_job_ready(parameters,legacy_job,tmp_path,monkeypatch,failure_at):
    job=pending.queue_job(parameters,job_directory=tmp_path/'job')
    monkeypatch.setattr(pending,'prepare_job',copied_preparer(legacy_job))
    original=pending.os.replace;calls=[]
    def fail(source,target):
        calls.append(target)
        if len(calls)==failure_at:raise OSError('injected promotion failure')
        return original(source,target)
    monkeypatch.setattr(pending.os,'replace',fail)
    with pytest.raises(OSError,match='injected'):pending.finish_preparation(job)
    assert json.loads((job/'request.json').read_text(encoding='utf-8'))['preparation_pending'] is True
    assert (job/'geometry.npz').exists()==(failure_at==2)


def test_existing_numeric_file_and_job_directory_are_preserved(parameters,tmp_path):
    job=pending.queue_job(parameters,job_directory=tmp_path/'job')
    sentinel=job/'geometry.npz';sentinel.write_bytes(b'unchanged')
    with pytest.raises(ValueError,match='already contains'):pending.finish_preparation(job)
    with pytest.raises(FileExistsError):pending.queue_job(parameters,job_directory=job)
    assert sentinel.read_bytes()==b'unchanged'


@pytest.mark.parametrize('action',['generate','disk','mechanical','turbogrid','both'])
def test_supported_actions_are_frozen_unchanged(parameters,tmp_path,action):
    job=pending.queue_job(parameters,action,tmp_path/'job')
    assert json.loads((job/'request.json').read_text(encoding='utf-8'))['action']==action


def test_unknown_action_and_stator_rejected_without_creating_job(parameters,tmp_path):
    with pytest.raises(ValueError,match='Unknown CAD action'):
        pending.queue_job(parameters,'unknown',tmp_path/'unknown')
    params=BladeParameters();params.blade_rows=initial_rows(params);params.active_blade_row='row-2'
    with pytest.raises(ValueError,match='Impeller'):
        pending.queue_job(params,job_directory=tmp_path/'stator')
    assert not (tmp_path/'unknown').exists() and not (tmp_path/'stator').exists()


def test_numeric_cli_failure_writes_diagnostic_without_outputs(parameters,tmp_path):
    job=pending.queue_job(parameters,job_directory=tmp_path/'job')
    (job/'geometry_snapshot.json').write_text('{}',encoding='utf-8')
    result=subprocess.run([sys.executable,'-X','utf8','-m','blade_designer.cad.pending_job',str(job)],
        cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==1
    report=json.loads((job/'result.json').read_text(encoding='utf-8'))
    assert report['overall']=='FAIL' and report['artifacts']=={}
    assert report['error']['stage']=='NUMERIC PREPARATION'
    assert 'hash mismatch' in (job/'error.log').read_text(encoding='utf-8')
    assert not (job/'geometry.npz').exists() and not (job/'outputs').exists()


@pytest.mark.parametrize('state',['pending','cancelled','failed_preparation'])
def test_direct_publication_rejects_incomplete_or_cancelled_job(parameters,legacy_job,tmp_path,state):
    if state=='pending':job=pending.queue_job(parameters,job_directory=tmp_path/'job')
    else:
        job=tmp_path/'job';shutil.copytree(legacy_job,job)
    report={'overall':'FAIL','artifacts':{}}
    if state=='cancelled':report['cancelled']=True
    if state=='failed_preparation':report['failed_phase']='preparation'
    (job/'result.json').write_text(json.dumps(report),encoding='utf-8')
    case=tmp_path/'case';case.mkdir();sentinel=case/'existing.step';sentinel.write_bytes(b'previous valid output')
    with pytest.raises(CadExportError,match='no files published'):publish_job(job,case,parameters)
    assert sentinel.read_bytes()==b'previous valid output'
    assert sorted(path.name for path in case.iterdir())==['existing.step']


def test_changed_ready_snapshot_cannot_be_copied_as_verified_output(parameters,legacy_job,tmp_path):
    job=tmp_path/'job';shutil.copytree(legacy_job,job)
    source=job/'geometry_snapshot.json';data=json.loads(source.read_text(encoding='utf-8'))
    data['cad_export']['fillet']['hub_radius_mm']=3.5;source.write_text(json.dumps(data),encoding='utf-8')
    request=json.loads((job/'request.json').read_text(encoding='utf-8'))
    (job/'result.json').write_text(json.dumps({'overall':'PASS','parameter_snapshot_hash':request['parameter_snapshot_hash'],'artifacts':{}}),encoding='utf-8')
    case=tmp_path/'case';case.mkdir();(case/'old.step').write_bytes(b'keep')
    with pytest.raises(ValueError,match='snapshot file hash mismatch'):publish_job(job,case,parameters)
    assert (case/'old.step').read_bytes()==b'keep' and len(list(case.iterdir()))==1
