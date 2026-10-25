from copy import deepcopy
from pathlib import Path
import pytest

from test_coordinate_proposal_io import source_study, queue, protected_files, next_source
from test_multiobjective import OBJECTIVES
from blade_designer.fileio.coordinate_study import export_study, read_study, import_results
from blade_designer.fileio.coordinate_proposal import validate_proposal_manifest


@pytest.fixture(scope='module')
def multi_source(tmp_path_factory, source_study):
    root=tmp_path_factory.mktemp('multi_source')
    spec=deepcopy(source_study[-1]);spec['objectives']=deepcopy(OBJECTIVES)
    original=protected_files(Path(spec['source_directory']))
    job=queue(root,source_study,spec=spec)
    assert export_study(job)['overall']=='PASS'
    _,manifest=read_study(root/'next')
    assert protected_files(Path(spec['source_directory']))==original
    return root/'next',manifest


def test_multiobjective_export_resume_and_actual_results_remain_pending(multi_source):
    directory,manifest=multi_source
    assert manifest['proposal']['objectives']==OBJECTIVES
    assert manifest['proposal']['selection']=='nondominated_fronts_crowding'
    assert all(set(c['prediction']['metrics'])=={'quality','pressure'} for c in manifest['cases'][1:])
    assert all(c['prediction']['status']=='PREDICTED_NOT_EVALUATED' for c in manifest['cases'][1:])
    assert all(r['status']=='pending' for r in import_results(directory/'external_results_template.csv',manifest).values())
    assert manifest['cfd']=='NOT_EXECUTED' and manifest['cad']=='NOT_EVALUATED'


def test_multiobjective_history_reuses_real_results_across_iterations(tmp_path,multi_source,source_study):
    source=next_source(multi_source[0],source_study)
    spec=deepcopy(source[-1]);spec['objectives']=deepcopy(OBJECTIVES)
    job=queue(tmp_path,source,spec=spec)
    assert export_study(job)['overall']=='PASS'
    _,manifest=read_study(tmp_path/'next')
    assert manifest['proposal']['training_count']==13
    assert manifest['proposal']['objectives']==OBJECTIVES
    assert any(o['id'].startswith(multi_source[1]['run_id']+'/') for o in manifest['proposal']['observations'])


@pytest.mark.parametrize('invalid',['duplicate','direction','missing_prediction','bad_cv','strategy','selection'])
def test_malformed_multiobjective_metadata_is_rejected(multi_source,invalid):
    manifest=deepcopy(multi_source[1]);proposal=manifest['proposal']
    if invalid=='duplicate':proposal['objectives'][1]=deepcopy(proposal['objectives'][0])
    elif invalid=='direction':proposal['maximize']=False
    elif invalid=='missing_prediction':manifest['cases'][1]['prediction']['metrics'].pop('pressure')
    elif invalid=='bad_cv':proposal['validation_metrics']['pressure']['cv_rmse']=1e100
    elif invalid=='strategy':manifest['cases'][1]['prediction']['strategy']='predicted_objective'
    else:proposal['selection']='weighted_sum'
    with pytest.raises(ValueError):validate_proposal_manifest(manifest)


def test_invalid_secondary_objective_refused_before_job_creation(tmp_path,source_study):
    spec=deepcopy(source_study[-1]);spec['objectives']=[OBJECTIVES[0],OBJECTIVES[0]]
    with pytest.raises(ValueError):queue(tmp_path,source_study,spec=spec)
    assert not (tmp_path/'job').exists()
