from copy import deepcopy
from dataclasses import replace
import csv
import hashlib
import json
import shutil
from pathlib import Path
import pytest

from blade_designer.fileio.project_io import load_project
from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions
from blade_designer.fileio.coordinate_study import (queue_study, export_study, read_study,
    digest, json_bytes, import_results, rank_results)
from blade_designer.optimization.coordinate_parameters import CoordinateStudy


CONTEXT='SIMULATED_TEST_DATA_ONLY'


@pytest.fixture(scope='module')
def source_study(tmp_path_factory):
    root=tmp_path_factory.mktemp('rbf_source')
    study=CoordinateStudy(load_project(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json'))
    variables=[replace(study.variables[0],lower=-.2,upper=.2,enabled=True)]
    options=CoordinateCsvOptions(include_hub=True,include_shroud=True,wall_layout='separate')
    job=queue_study(study,variables,9,7,options,root/'source',job_directory=root/'source_job',evaluation_context=CONTEXT)
    assert export_study(job)['overall']=='PASS'
    _,manifest=read_study(root/'source')
    assert all(c['status']=='READY_FOR_EXTERNAL' for c in manifest['cases'])
    path=root/'results.csv'
    write_results(path,manifest)
    spec={'source_directory':str(root/'source'),'manifest_hash':digest(json_bytes(manifest)),
          'results_path':str(path),'results_hash':digest(path.read_bytes()),'objective':'quality',
          'maximize':True,'constraints':{}}
    return study,variables,options,manifest,spec


def write_results(path,manifest,statuses=None):
    statuses=statuses or {}
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['run_id','candidate_id','candidate_hash','evaluation_context','status','quality','pressure'])
        for case in manifest['cases']:
            x=next(iter(case['values'].values()),0.)/.2
            status=statuses.get(case['candidate_id'],'success')
            writer.writerow([manifest['run_id'],case['candidate_id'],case['candidate_hash'],CONTEXT,status,
                             1-(x-.25)**2 if status=='success' else '',2+x if status=='success' else ''])


def queue(tmp_path,source_study,*,spec=None,variables=None,context=CONTEXT):
    study,original,options,_,original_spec=source_study
    return queue_study(study,original if variables is None else variables,3,11,options,tmp_path/'next',
                       job_directory=tmp_path/'job',evaluation_context=context,
                       proposal=deepcopy(original_spec) if spec is None else spec)


def protected_files(source):
    return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source.rglob('*') if p.is_file()}


def test_end_to_end_proposal_export_resume_and_no_fake_results(tmp_path,source_study):
    _,variables,_,source,spec=source_study
    before=protected_files(Path(spec['source_directory']))
    job=queue(tmp_path,source_study)
    assert export_study(job)['overall']=='PASS'
    _,manifest=read_study(tmp_path/'next')
    assert manifest['sampling']=='rbf_external' and len(manifest['cases'])==4
    assert manifest['proposal']['source_run_id']==source['run_id']
    assert manifest['proposal']['source_results_sha256']==spec['results_hash']
    assert manifest['proposal']['training_count']==10
    assert manifest['cfd']=='NOT_EXECUTED' and manifest['cad']=='NOT_EVALUATED'
    assert all(c['prediction']['status']=='PREDICTED_NOT_EVALUATED' for c in manifest['cases'][1:])
    assert not {tuple(c['values'].items()) for c in manifest['cases'][1:]} & {tuple(c['values'].items()) for c in source['cases']}
    for case in manifest['cases'][1:]:
        assert set(case['values'])=={variables[0].key} and case['status']=='READY_FOR_EXTERNAL'
    results=import_results(tmp_path/'next/external_results_template.csv',manifest)
    assert rank_results(results,'quality')==[] and all(r['status']=='pending' for r in results.values())
    assert protected_files(Path(spec['source_directory']))==before
    assert not list((tmp_path/'next').rglob('*.step'))


@pytest.mark.parametrize('change',['bounds','context','manifest','baseline','frozen_csv','wrong_run'])
def test_mismatched_data_rejected_before_new_output(tmp_path,source_study,change):
    study,variables,_,manifest,original_spec=source_study
    spec=deepcopy(original_spec);arguments={}
    if change=='bounds':arguments['variables']=[replace(variables[0],upper=.3)]
    elif change=='context':arguments['context']='DIFFERENT_OPERATING_POINT'
    elif change=='manifest':spec['manifest_hash']='0'*64
    elif change=='wrong_run':
        path=tmp_path/'wrong.csv';path.write_bytes(Path(spec['results_path']).read_bytes().replace(manifest['run_id'].encode(),b'wrong_run'))
        spec.update(results_path=str(path),results_hash=digest(path.read_bytes()))
    job=queue(tmp_path,source_study,spec=spec,**arguments)
    if change=='baseline':
        request=json.loads((job/'request.json').read_text());request['proposal']['source_directory']=spec['source_directory']
        # Source hash must be validated against the job, not only against itself.
        from blade_designer.fileio.preview_job import snapshot_text
        other=study.baseline;other.blade_rows[0].name+=' changed'
        data=snapshot_text(other).encode();(job/'snapshot.json').write_bytes(data)
        request['snapshot_hash']=digest(data);(job/'request.json').write_bytes(json_bytes(request))
    elif change=='frozen_csv':(job/'external-results.csv').write_text('modified')
    with pytest.raises(ValueError):export_study(job)
    assert not (tmp_path/'next').exists()


def test_csv_changed_after_import_is_rejected_without_creating_job(tmp_path,source_study):
    spec=deepcopy(source_study[-1]);path=tmp_path/'changed.csv'
    path.write_bytes(Path(spec['results_path']).read_bytes()+b'\n');spec['results_path']=str(path)
    with pytest.raises(ValueError,match='changed since import'):queue(tmp_path,source_study,spec=spec)
    assert not (tmp_path/'job').exists()


def test_frozen_results_survive_later_external_csv_edits(tmp_path,source_study):
    spec=deepcopy(source_study[-1]);path=tmp_path/'copy.csv';path.write_bytes(Path(spec['results_path']).read_bytes())
    spec['results_path']=str(path);job=queue(tmp_path,source_study,spec=spec)
    path.write_text('edited after queue')
    assert export_study(job)['overall']=='PASS'


def test_changed_source_coordinate_file_and_existing_output_are_protected(tmp_path,source_study):
    spec=deepcopy(source_study[-1]);copy=tmp_path/'source_copy'
    shutil.copytree(spec['source_directory'],copy);spec['source_directory']=str(copy)
    job=queue(tmp_path,source_study,spec=spec)
    name=next(iter(source_study[3]['cases'][0]['sha256']));(copy/name).write_text('changed')
    with pytest.raises(ValueError,match='changed'):export_study(job)
    target=tmp_path/'next';target.mkdir();(target/'keep.txt').write_text('keep')
    with pytest.raises(FileExistsError):export_study(job)
    assert (target/'keep.txt').read_text()=='keep'


def test_failed_and_pending_evaluations_excluded_and_too_few_refused(tmp_path,source_study):
    manifest=source_study[3];spec=deepcopy(source_study[-1]);path=tmp_path/'partial.csv'
    statuses={manifest['cases'][i]['candidate_id']:'failed' if i==0 else 'pending' for i in range(3)}
    write_results(path,manifest,statuses);spec.update(results_path=str(path),results_hash=digest(path.read_bytes()))
    job=queue(tmp_path,source_study,spec=spec)
    with pytest.raises(ValueError,match='8..250 complete'):export_study(job)
    assert not (tmp_path/'next').exists()


def test_predicted_candidate_still_needs_real_coordinate_generation(tmp_path,source_study,monkeypatch):
    import blade_designer.fileio.coordinate_study as module
    original=module.prepare_coordinate_csv
    baseline_hash=source_study[3]['baseline_hash']
    def fail_new_geometry(geometry,source,*args,**kwargs):
        if source.snapshot_hash!=baseline_hash:raise ValueError('Injected invalid proposal geometry')
        return original(geometry,source,*args,**kwargs)
    monkeypatch.setattr(module,'prepare_coordinate_csv',fail_new_geometry)
    job=queue(tmp_path,source_study);assert export_study(job)['overall']=='PASS'
    _,manifest=read_study(tmp_path/'next')
    assert all(c['status']=='FAILED' and not c['sha256'] for c in manifest['cases'][1:])
    assert not (tmp_path/'next/case_0001').exists()


def next_source(directory,original):
    study,manifest=read_study(directory)
    path=directory.parent/'evaluated.csv';write_results(path,manifest)
    spec={**original[-1],'source_directory':str(directory),'manifest_hash':digest(json_bytes(manifest)),
          'results_path':str(path),'results_hash':digest(path.read_bytes())}
    return study,original[1],original[2],manifest,spec


def test_iterations_accumulate_real_observations_and_keep_distinct_run_ids(tmp_path,source_study):
    first=tmp_path/'first';first.mkdir();job=queue(first,source_study);export_study(job)
    source2=next_source(first/'next',source_study)
    second=tmp_path/'second';second.mkdir();job=queue(second,source2);export_study(job)
    _,manifest=read_study(second/'next');proposal=manifest['proposal']
    assert proposal['training_count']==13  # Original 10, repeated baseline replaced, 3 genuinely new.
    assert len(proposal['replaced_observations'])==1
    assert len({o['id'] for o in proposal['observations']})==13
    assert {o['id'].split('/')[0] for o in proposal['observations']}=={source_study[3]['run_id'],source2[3]['run_id']}
    attempted={tuple(sorted(v.items())) for v in proposal['seen_vectors']}
    assert all(tuple(sorted(c['values'].items())) not in attempted for c in manifest['cases'][1:])


def test_iteration_cannot_learn_from_predictions_or_pending_results(tmp_path,source_study):
    first=tmp_path/'first';first.mkdir();export_study(queue(first,source_study))
    source2=next_source(first/'next',source_study)
    path=Path(source2[-1]['results_path'])
    write_results(path,source2[3],{c['candidate_id']:'pending' for c in source2[3]['cases']})
    source2[-1]['results_hash']=digest(path.read_bytes())
    second=tmp_path/'second';second.mkdir();job=queue(second,source2)
    with pytest.raises(ValueError,match='at least one new candidate'):export_study(job)
    assert not (second/'next').exists()


def test_failed_repeat_invalidates_old_observation_and_new_constraint_uses_real_history(tmp_path,source_study):
    first=tmp_path/'first';first.mkdir();export_study(queue(first,source_study))
    source2=next_source(first/'next',source_study)
    path=Path(source2[-1]['results_path']);write_results(path,source2[3],{'case_0000':'failed'})
    source2[-1].update(results_hash=digest(path.read_bytes()),constraints={'pressure':(1.,3.)})
    second=tmp_path/'second';second.mkdir();export_study(queue(second,source2))
    _,manifest=read_study(second/'next');proposal=manifest['proposal']
    assert proposal['training_count']==12 and len(proposal['invalidated_observations'])==1
    assert all('pressure' in o['metrics'] for o in proposal['observations'])
    assert 'pressure' in proposal['validation_metrics']


@pytest.fixture(scope='module')
def proposed_source(tmp_path_factory,source_study):
    root=tmp_path_factory.mktemp('proposed_study');export_study(queue(root,source_study))
    return root/'next',read_study(root/'next')[1]


@pytest.mark.parametrize('invalid',['prediction_type','fake_status','nonfinite','invalid_validation'])
def test_malformed_predictions_rejected_before_display(proposed_source,invalid):
    from blade_designer.fileio.coordinate_proposal import validate_proposal_manifest
    manifest=deepcopy(proposed_source[1])
    if invalid=='prediction_type':manifest['cases'][1]['prediction']='wrong'
    elif invalid=='fake_status':manifest['cases'][1]['prediction']['status']='EXTERNALLY_VERIFIED'
    elif invalid=='nonfinite':manifest['cases'][1]['prediction']['metrics']['quality']=float('nan')
    else:manifest['proposal']['validation_metrics']['quality']['cv_rmse']=-1.
    with pytest.raises(ValueError,match='RBF'):validate_proposal_manifest(manifest)


def test_changed_history_configuration_cannot_be_reused(tmp_path,proposed_source,source_study):
    directory=tmp_path/'source';shutil.copytree(proposed_source[0],directory)
    manifest=deepcopy(proposed_source[1]);manifest['proposal']['history_configuration_sha256']='0'*64
    (directory/'manifest.json').write_bytes(json_bytes(manifest))
    source2=next_source(directory,source_study)
    target=tmp_path/'target';target.mkdir();job=queue(target,source2)
    with pytest.raises(ValueError,match='history configuration'):export_study(job)
    assert not (target/'next').exists()


@pytest.mark.parametrize('count',[0,51])
def test_proposal_batch_limit_checked_before_job_creation(tmp_path,source_study,count):
    study,variables,options,_,spec=source_study
    with pytest.raises(ValueError,match='1..50'):
        queue_study(study,variables,count,7,options,tmp_path/'next',job_directory=tmp_path/'job',proposal=spec)
    assert not (tmp_path/'job').exists()


def test_oversized_external_csv_rejected_without_reading_unbounded_file(tmp_path,source_study):
    spec=deepcopy(source_study[-1]);path=tmp_path/'large.csv';path.write_bytes(b'x'*(4*1024*1024+1))
    spec.update(results_path=str(path),results_hash=digest(path.read_bytes()))
    with pytest.raises(ValueError,match='4 MiB'):queue(tmp_path,source_study,spec=spec)
    assert not (tmp_path/'job').exists()


def test_import_fingerprint_reads_bounded_chunks_and_matches_independent_hash(tmp_path,monkeypatch):
    from blade_designer.fileio.coordinate_study import file_sha256
    payload=b'CSV fingerprint data\n'*150000
    path=tmp_path/'large-results.csv';path.write_bytes(payload)
    original=Path.open;reads=[]
    class Bounded:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):self.stream.close()
        def read(self,size=-1):
            assert 0<size<=1024*1024
            reads.append(size);return self.stream.read(size)
    def opening(p,*args,**kwargs):
        stream=original(p,*args,**kwargs)
        return Bounded(stream) if p==path and args and args[0]=='rb' else stream
    monkeypatch.setattr(Path,'open',opening)
    assert file_sha256(path)==hashlib.sha256(payload).hexdigest()
    assert len(reads)>=3
