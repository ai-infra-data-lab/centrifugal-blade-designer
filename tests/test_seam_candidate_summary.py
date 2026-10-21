"""Inventory completeness is distinct from local numerical success."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.seam_candidate_summary import seam_candidate_summary
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
from test_seam_contact_refinement import fixture


def scan(source,envelope,**options):
    return seam_candidate_summary(source,envelope,**{'gap_tolerance_mm':1e-8,
        'reference_min_mm':1e-12,'monotonic_margin':0.,'nonadjacent_clearance_mm':0.,**options})


def test_complete_inventory_matches_independent_all_face_pairs_and_preserves_sources():
    source,envelope=fixture();old=deepcopy(envelope)
    nets={r:s.across.c.copy() for r,s in source.items()}
    report=scan(source,envelope)
    mesh=envelope['mesh'];faces=mesh['faces'];roles=mesh['face_roles']
    expected=[[a,b] for a in range(len(faces)) for b in range(a+1,len(faces))
              if roles[a]!=roles[b] and set(faces[a]) & set(faces[b])]
    assert [r['faces'] for r in report['records']]==expected
    assert report['status']=='DIAGNOSTICS_RECORDED' and report['candidate_count_is_total']
    assert sum(report['counts'].values())==len(expected)>0
    assert all(r['expected_parameter_contact_only'] for r in report['records'])
    assert not report['whole_geometry_verified'] and not report['export_ready']
    for r,s in source.items():np.testing.assert_array_equal(s.across.c,nets[r])
    np.testing.assert_array_equal(envelope['mesh']['vertices'],old['mesh']['vertices'])
    assert report==scan(source,envelope)


@pytest.mark.parametrize('options,reason',[(dict(max_pair_visits=1),'max_pair_visits'),
                                        (dict(max_candidates=1),'max_candidates')])
def test_inventory_limit_is_not_a_total(options,reason):
    report=scan(*fixture(),**options)
    assert report['status']=='RESOURCE_LIMIT' and not report['inventory_complete']
    assert not report['candidate_count_is_total'] and report['inventory_stop_reason']==reason
    assert not report['export_ready']


def test_evaluation_cap_keeps_explicit_unexamined_records():
    report=scan(*fixture(),max_evaluated=1)
    assert report['inventory_complete'] and report['candidate_count_is_total']
    assert report['status']=='RESOURCE_LIMIT' and report['counts']['UNEXAMINED']>0
    assert all(r['chart_report'] is None for r in report['records'][1:])


def test_tiny_gap_inside_budget_never_becomes_expected_contact():
    source,_=fixture();source['ps'].across.c[:,:,0]+=1e-12
    envelope=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)
    report=scan(source,envelope)
    mismatches=[r for r in report['records'] if r['identity_report'] and
                r['identity_report']['same_parameter_curve_exact_model'] is False]
    assert mismatches
    for record in mismatches:
        assert record['gap_report']['status']=='NUMERIC_WITHIN_GAP_TOLERANCE'
        assert record['status']=='UNRESOLVED' and not record['expected_parameter_contact_only']
    assert not report['export_ready']


def test_zero_gap_budget_records_observed_difference_separately():
    source,_=fixture();source['ps'].across.c[:,:,0]+=1e-12
    envelope=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)
    report=scan(source,envelope,gap_tolerance_mm=0.)
    observed=[r for r in report['records'] if r['gap_report'] and
              r['gap_report']['status']=='GAP_OBSERVED']
    assert observed and all(r['status']=='UNRESOLVED' for r in observed)
    assert report['inventory_complete'] and report['evaluation_complete']
    assert not report['physical_gap_certified'] and not report['export_ready']


def test_unexamined_records_do_not_share_mutable_diagnostic_objects():
    source,envelope=fixture();report=scan(source,envelope)
    records=report['records'];records[0]['gap_report']['status']='changed by consumer'
    assert all(r['gap_report']['status']!='changed by consumer' for r in records[1:])
    assert scan(source,envelope)['records'][0]['gap_report']['status']!='changed by consumer'


@pytest.mark.parametrize('change',['source','mapping','missing'])
def test_stale_or_missing_binding_rejected(change):
    source,envelope=fixture()
    if change=='source':source['ps'].across.c[:,:,0]+=1
    elif change=='mapping':envelope['mesh']['faces'][0,0]=1
    else:envelope.pop('mapping_fingerprint')
    with pytest.raises(ValueError):scan(source,envelope)


@pytest.mark.parametrize('options',[{'max_candidates':0},{'max_candidates':True},
    {'max_evaluated':0},{'max_pair_visits':False},{'max_triangles':0},
    {'gap_tolerance_mm':-1},{'gap_tolerance_mm':float('nan')},
    {'reference_min_mm':-1},{'monotonic_margin':float('inf')},
    {'nonadjacent_clearance_mm':-1}])
def test_invalid_options(options):
    with pytest.raises(ValueError):scan(*fixture(),**options)
