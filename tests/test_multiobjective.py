from copy import deepcopy
import numpy as np
import pytest

from blade_designer.optimization.pareto import objective_definitions, pareto_order
from blade_designer.optimization.surrogate_proposals import propose_candidates
from blade_designer.fileio.coordinate_study import pareto_results
from test_surrogate_proposals import fixture, observations


OBJECTIVES = [{'name': 'quality', 'maximize': True}, {'name': 'pressure', 'maximize': False}]


def test_analytic_mixed_directions_fronts_ties_and_crowding_extremes():
    # max first/min second: indices 0,1,2,4 trade off; index3 is dominated.
    order, ranks = pareto_order([[1, 1], [2, 2], [3, 3], [1, 3], [2, 2]], [True, False])
    assert ranks == [1, 1, 1, 2, 1]
    assert set(order[:2]) == {0, 2}
    assert sorted(order) == list(range(5)) and order[-1] == 3


def test_identical_vectors_constant_axis_empty_and_dominance_chain():
    assert pareto_order([[1, 1]]*3, [True, True]) == ([0, 1, 2], [1, 1, 1])
    assert pareto_order([[1, 0], [2, 0], [3, 0]], [True, False]) == ([2, 1, 0], [3, 2, 1])
    assert pareto_order(np.empty((0, 2)), [True, False]) == ([], [])


def test_dominance_keeps_tiny_distinct_values_in_a_large_dynamic_range():
    # Range normalization may underflow for crowding, but must not invent ties.
    assert pareto_order([[1e308,1.], [1e-308,1.], [0.,1.]], [True,False]) == ([0,1,2], [1,2,3])


@pytest.mark.parametrize('factor', [1e-20, 1e20])
def test_fronts_and_crowding_are_invariant_to_positive_objective_units(factor):
    values=np.array([[1., 1.], [2., 2.], [3., 3.], [1., 4.]])
    assert pareto_order(values, [True, False]) == pareto_order(values*[factor, 1.], [True, False])


@pytest.mark.parametrize('definitions', [[], [{'name':'a','maximize':True}],
    [{'name':'a','maximize':True}]*2,
    [{'name':'a','maximize':1}, {'name':'b','maximize':False}],
    [{'name':'a','maximize':True}, {'name':' ','maximize':False}]])
def test_invalid_objective_definitions_rejected(definitions):
    with pytest.raises(ValueError): objective_definitions(definitions)


def test_nonfinite_or_excessive_pareto_input_is_rejected():
    with pytest.raises(ValueError): pareto_order([[1.,float('nan')]], [True,False])
    with pytest.raises(ValueError): pareto_order(np.zeros((2049,2)), [True,False])


def test_external_pareto_uses_only_complete_successful_feasible_actual_values():
    results={key:{'status':status,'metrics':{'quality':q,'pressure':p,'limit':limit}}
             for key,status,q,p,limit in [('a','success',1,1,0),('b','success',2,2,0),
                ('c','success',1,2,0),('pending','pending',9,0,0),('failed','failed',9,0,0),
                ('missing','success',5,None,0),('constraint','success',10,0,2)]}
    before=deepcopy(results)
    order,ranks=pareto_results(results,OBJECTIVES,{'limit':(None,1)})
    assert set(order[:2])=={'a','b'} and ranks=={'a':1,'b':1,'c':2}
    assert results==before


def test_multiobjective_proposals_cover_conflicting_extremes_and_preserve_inputs():
    study,variables=fixture();rows=observations(variables)
    # Linear opposing objectives have an analytically known trade-off everywhere.
    for o in rows:
        x=o['values'][variables[0].key];o['metrics']={'quality':x, 'pressure':x}
    before=deepcopy(rows)
    kwargs=dict(objectives=OBJECTIVES)
    batch=propose_candidates(study,variables,rows,[o['values'] for o in rows],4,7,'quality',**kwargs)
    values=[v[variables[0].key] for v in batch['vectors']]
    assert min(values)<-.9 and max(values)>.9
    assert [p['strategy'] for p in batch['predictions']]==['predicted_pareto']*3+['space_filling']
    assert all(set(p['metrics'])=={'quality','pressure'} for p in batch['predictions'])
    assert rows==before
    assert batch==propose_candidates(study,variables,rows,[o['values'] for o in rows],4,7,'quality',**kwargs)


@pytest.mark.parametrize('invalid', ['missing', 'constant', 'noise'])
def test_every_objective_must_have_complete_validated_information(invalid):
    study,variables=fixture();rows=observations(variables)
    if invalid=='missing': rows[0]['metrics']['pressure']=None
    elif invalid=='constant':
        for o in rows:o['metrics']['pressure']=1.
    else:
        for i,o in enumerate(rows):o['metrics']['pressure']=float((-1)**i)
    with pytest.raises(ValueError):
        propose_candidates(study,variables,rows,[],4,7,'quality',objectives=OBJECTIVES)


def test_multiobjective_constraint_and_attempted_vector_protection():
    study,variables=fixture();rows=observations(variables)
    for o in rows:
        x=o['values'][variables[0].key];o['metrics']={'quality':x, 'pressure':x}
    batch=propose_candidates(study,variables,rows,[],3,7,'quality',
                             constraints={'pressure':(-.4,.4)},objectives=OBJECTIVES)
    assert all(-.4<=p['metrics']['pressure']<=.4 for p in batch['predictions'])
    seen=[*[o['values'] for o in rows],*batch['vectors']]
    next_batch=propose_candidates(study,variables,rows,seen,3,7,'quality',
                                  constraints={'pressure':(-.4,.4)},objectives=OBJECTIVES)
    assert not {tuple(v.items()) for v in batch['vectors']} & {tuple(v.items()) for v in next_batch['vectors']}
