"""Projection choice and independent reasons must not relax adoption conditions."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
from test_seam_candidate_summary import scan
from test_seam_contact_refinement import fixture
from test_seam_injectivity import bezier
from test_seam_projection_strategies import kink


def kink_fixture():
    first,second=kink(.1)
    first.across.c=first.across.c[:,::-1].copy()
    def wall(a,b):
        return bezier([[a,b],[np.array(a)+[0,1,0],np.array(b)+[0,1,0]]])
    source={'le':first,'ps':second,'te':wall([-.8,0,.6],[-2,0,1]),
            'ss':wall([-.1,0,0],[-2,0,1])}
    return source,merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)


def test_default_and_explicit_average_preserve_all_reports():
    source,envelope=fixture()
    implicit=scan(source,envelope)
    assert implicit==scan(source,envelope,projection_strategy='average')
    assert implicit['projection_strategy']=='average'
    for key in ('identity_status','gap_status','chart_status','chart_root_reason','chart_union_reason'):
        assert sum(implicit['diagnostic_counts'][key].values())==implicit['discovered_candidates']


def test_balanced_projection_resolves_analytic_kink_without_changing_domain_or_thresholds():
    source,envelope=kink_fixture();before=deepcopy(source)
    average=scan(source,envelope);balanced=scan(source,envelope,projection_strategy='balanced_transverse')
    a=next(r for r in average['records'] if r['faces']==[1,2])
    b=next(r for r in balanced['records'] if r['faces']==[1,2])
    assert a['status']=='UNRESOLVED' and b['expected_parameter_contact_only']
    assert a['identity_report']==b['identity_report'] and a['gap_report']==b['gap_report']
    ar=a['chart_report']['union_report']['partition_report']['root_report']
    br=b['chart_report']['union_report']['partition_report']['root_report']
    for key in ('span_range','widths','reference_min_mm','monotonic_margin','source_fingerprints'):
        assert ar[key]==br[key]
    assert br['min_symmetric_lower']==pytest.approx(2/11)
    assert balanced['mapping_fingerprint']==average['mapping_fingerprint']
    for role in source:np.testing.assert_array_equal(source[role].across.c,before[role].across.c)
    for record in balanced['records']:
        partition=record['chart_report']['union_report']['partition_report']
        assert all(n['report']['projection_strategy']=='balanced_transverse' for n in partition['charts'])
    assert not balanced['export_ready'] and not balanced['whole_geometry_verified']


@pytest.mark.parametrize('strategy',['average','balanced_transverse'])
def test_gap_and_chart_reasons_remain_separate_even_inside_gap_budget(strategy):
    source,_=fixture();source['ps'].across.c[:,:,0]+=1e-12
    envelope=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)
    report=scan(source,envelope,projection_strategy=strategy);counts=report['diagnostic_counts']
    n=counts['identity_status']['EXACT_PARAMETER_CURVE_DIFFERENCE']
    assert n>0 and counts['unresolved_identity_status']['EXACT_PARAMETER_CURVE_DIFFERENCE']==n
    assert counts['chart_root_reason']['boundary_representation_mismatch']==n
    assert counts['chart_stop_reasons']['boundary_representation_mismatch']==n
    assert counts['gap_status']['NUMERIC_WITHIN_GAP_TOLERANCE']==report['discovered_candidates']


def test_unexamined_are_visible_in_each_diagnostic_dimension():
    report=scan(*fixture(),max_evaluated=1);n=report['discovered_candidates']-1
    for key in ('identity_status','gap_status','chart_status','chart_root_reason','chart_union_reason','chart_stop_reasons'):
        assert report['diagnostic_counts'][key]['NOT_EVALUATED:UNEXAMINED']==n
    assert sum(report['diagnostic_counts']['unresolved_identity_status'].values())==0


def test_stop_reason_counts_candidates_not_stopped_nodes():
    report=scan(*kink_fixture());count=0
    for record in report['records']:
        stops=record['chart_report']['union_report']['partition_report']['stop_reasons']
        if 'max_depth' in stops:count+=1
    assert count>0 and report['diagnostic_counts']['chart_stop_reasons']['max_depth']==count


@pytest.mark.parametrize('strategy',[None,True,1,[],{},'auto','balanced'])
def test_unknown_strategy_rejected_before_inventory_or_partial_evaluation(strategy):
    with pytest.raises(ValueError,match='projection_strategy'):
        scan(*fixture(),projection_strategy=strategy,max_pair_visits=1)
