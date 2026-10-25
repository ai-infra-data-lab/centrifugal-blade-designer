from copy import deepcopy
from dataclasses import replace
import numpy as np
import pytest

from blade_designer.models.parameters import BladeParameters
from blade_designer.models.blade_rows import initial_rows
from blade_designer.optimization.coordinate_parameters import CoordinateStudy
from blade_designer.optimization.surrogate_proposals import propose_candidates


def fixture(dimension=1):
    project=BladeParameters();project.blade_rows=initial_rows(project)
    project.active_blade_row=project.blade_rows[0].identifier
    study=CoordinateStudy(project)
    variables=[replace(v,lower=-1.,upper=1.,enabled=True) for v in study.variables[:dimension]]
    return study,variables


def observations(variables, count=12):
    return [{'id':str(i),'values':{v.key:float(x) for v in variables},
             'metrics':{'quality':1-(x-.25)**2,'pressure':float(x)}}
            for i,x in enumerate(np.linspace(-1,1,count))]


def run(study,variables,rows,**kwargs):
    return propose_candidates(study,variables,rows,[o['values'] for o in rows],
                              kwargs.pop('count',4),kwargs.pop('seed',7),'quality',**kwargs)


def test_analytic_quadratic_maximum_and_predictions_are_separate_and_reproducible():
    study,variables=fixture();rows=observations(variables);before=deepcopy((study.baseline,variables,rows))
    batch=run(study,variables,rows);repeat=run(study,variables,rows)
    assert batch==repeat
    assert abs(batch['vectors'][0][variables[0].key]-.25)<.1
    validation=batch['diagnostics']['validation_metrics']['quality']
    # Boundary holdouts require extrapolation even for this analytic case.
    # Check the declared mean-predictor gate, not an unsupported absolute error.
    assert 0<validation['cv_rmse']<validation['mean_predictor_rmse']
    assert batch['diagnostics']['uncertainty']=='NOT_ESTIMATED'
    assert len(batch['vectors'])==4 and batch['predictions'][-1]['strategy']=='space_filling'
    assert all(p['status']=='PREDICTED_NOT_EVALUATED' for p in batch['predictions'])
    assert (study.baseline,variables,rows)==before


def test_minimization_and_predicted_metric_constraints():
    study,variables=fixture();rows=observations(variables)
    for o in rows:
        x=o['values'][variables[0].key];o['metrics']['quality']=(x+.35)**2
    batch=run(study,variables,rows,maximize=False)
    assert abs(batch['vectors'][0][variables[0].key]+.35)<.1
    batch=run(study,variables,rows,maximize=False,constraints={'pressure':(.6,None)})
    assert all(v[variables[0].key]>=.6-1e-10 for v in batch['vectors'])
    assert all(p['metrics']['pressure']>=.6 for p in batch['predictions'])


def test_linked_hub_tip_and_multiple_rows_share_one_axis():
    study,_=fixture()
    variables=[replace(v,lower=-1.,upper=1.,enabled=True,link='exit') for v in study.variables
               if study._targets[v.key][-1]=='beta_te']
    assert len(variables)>=3
    batch=run(study,variables,observations(variables))
    assert batch['diagnostics']['independent_dimensions']==1
    assert all(len(set(v.values()))==1 and len(v)==len(variables) for v in batch['vectors'])


def test_independent_two_variable_plane_and_nongeometry_core(monkeypatch):
    study,variables=fixture(2);rows=[]
    for i,(x,y) in enumerate(( (x,y) for x in (-1.,0.,1.) for y in (-1.,-.3,.3,1.) )):
        rows.append({'id':str(i),'values':dict(zip([v.key for v in variables],(x,y))),
                     'metrics':{'quality':x+2*y}})
    monkeypatch.setattr(study,'candidate',lambda *a:pytest.fail('No geometry construction in surrogate core'))
    batch=run(study,variables,rows)
    assert batch['diagnostics']['independent_dimensions']==2
    assert batch['predictions'][0]['metrics']['quality']>2.7
    for vector in batch['vectors']:study.check_vector(vector,variables)


def test_all_source_vectors_excluded_even_if_not_used_for_training():
    study,variables=fixture();rows=observations(variables)
    first=run(study,variables,rows,count=1)['vectors'][0]
    batch=propose_candidates(study,variables,rows,[*[o['values'] for o in rows],first],1,7,'quality')
    assert abs(batch['vectors'][0][variables[0].key]-first[variables[0].key])>2e-5


@pytest.mark.parametrize('count',[0,True,51])
def test_invalid_batch_size_rejected(count):
    study,variables=fixture()
    with pytest.raises(ValueError):run(study,variables,observations(variables),count=count)


def test_too_few_high_dimensional_or_duplicate_data_rejected():
    study,variables=fixture()
    with pytest.raises(ValueError,match='8..250'):run(study,variables,observations(variables,7))
    rows=observations(variables);rows[-1]['values']=deepcopy(rows[0]['values'])
    with pytest.raises(ValueError,match='indistinguishable'):run(study,variables,rows)
    study,variables=fixture(2)
    with pytest.raises(ValueError,match='span'):run(study,variables,observations(variables))


@pytest.mark.parametrize('invalid',[None,True,float('nan'),float('inf')])
def test_missing_or_invalid_observation_never_replaced_by_zero(invalid):
    study,variables=fixture();rows=observations(variables);rows[0]['metrics']['quality']=invalid
    with pytest.raises(ValueError,match='finite'):run(study,variables,rows)


def test_uninformative_and_unvalidated_objectives_are_not_proposed():
    study,variables=fixture();rows=observations(variables)
    for o in rows:o['metrics']['quality']=1.
    with pytest.raises(ValueError,match='variation'):run(study,variables,rows)
    for i,o in enumerate(rows):o['metrics']['quality']=float((-1)**i)
    with pytest.raises(ValueError,match='not better'):run(study,variables,rows)


def test_impossible_predicted_constraints_fail_without_relaxing_limits():
    study,variables=fixture()
    with pytest.raises(ValueError,match='predicted-feasible'):
        run(study,variables,observations(variables),constraints={'pressure':(5.,6.)})


def test_constant_observed_constraint_is_not_reported_as_proven_feasible():
    study,variables=fixture();rows=observations(variables)
    for o in rows:o['metrics']['pressure']=3.
    batch=run(study,variables,rows,constraints={'pressure':(2.,4.)})
    assert batch['diagnostics']['validation_metrics']['pressure']['constant_observed']
    assert batch['diagnostics']['feasibility']=='PREDICTED_ONLY'


@pytest.mark.parametrize('factor',[1e-20,1e20])
def test_positive_metric_unit_rescaling_preserves_proposals_and_error_units(factor):
    study,variables=fixture();rows=observations(variables)
    ordinary=run(study,variables,rows)
    for row in rows:
        row['metrics']['quality']*=factor
    scaled=run(study,variables,rows)
    np.testing.assert_array_equal([v[variables[0].key] for v in ordinary['vectors']],
                                  [v[variables[0].key] for v in scaled['vectors']])
    original=ordinary['diagnostics']['validation_metrics']['quality']['cv_rmse']
    assert scaled['diagnostics']['validation_metrics']['quality']['cv_rmse']/factor==pytest.approx(original,rel=1e-10)
