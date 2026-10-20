"""Complete pair coverage, analytic self crossing and conservative hull failures."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.seam_chart_union import seam_union_injectivity,local_seam_union_injectivity,_hull_points
from test_seam_contact_refinement import shear,fixture
from test_seam_injectivity import strips,bezier
from test_surface_envelope import patch
from test_role_seams import tube
from blade_designer.geometry.merged_role_error import merged_role_error_envelope


def check(a,b,**options):
    return seam_union_injectivity(a,0,b,0,**{'first_width':1.,'second_width':1.,
        'reference_min_mm':1e-12,'monotonic_margin':0.,'nonadjacent_clearance_mm':0.,**options})


def test_root_proof_needs_no_cross_chart_inference():
    r=check(*strips())
    assert r['numeric_injective'] and r['reason']=='root_chart' and not r['pair_records']
    assert not r['cross_chart_pairs_checked'] and r['required_pairs']==0
    assert not r['whole_geometry_verified'] and not r['roundoff_certified']


def test_analytic_shear_union_uses_collars_and_all_nonadjacent_pairs():
    a,b=shear();before=deepcopy((a.across.c,b.across.c));r=check(a,b)
    assert r['status']=='NUMERIC_INJECTIVE_ON_CHART_UNION' and r['numeric_injective']
    assert not r['partition_report']['numeric_injective']
    assert r['partition_report']['status']=='LOCAL_CHARTS_ONLY'
    assert r['required_pairs']==6 and len(r['pair_records'])==6
    assert r['pair_scan_complete'] and r['cross_chart_pairs_checked']
    assert {(p['first_leaf'],p['second_leaf']) for p in r['pair_records']}=={(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)}
    for pair in r['pair_records']:
        if pair['second_leaf']==pair['first_leaf']+1:
            assert pair['collar_report']['numeric_injective'] and len(pair['separations'])==2
        else:assert pair['collar_report'] is None and len(pair['separations'])==1
        assert pair['numeric_compatible']
    for s,old in zip((a,b),before):np.testing.assert_array_equal(s.across.c,old)
    assert not r['continuous_surface_certified'] and not r['coordinates_modified']


def test_locally_regular_analytic_self_crossing_cannot_be_promoted_to_union_success():
    # x=48s²-48s+9, y=48s³-72s²+33s-4.5. C(.25)=C(.75)=(0,0).
    xy=np.array([[9,-4.5],[-7,6.5],[-7,-6.5],[9,4.5]])
    sources=[]
    for sign in (-1,1):
        net=np.empty((4,2,3));net[:,:,:2]=xy[:,None];net[:,:,2]=[0,sign]
        sources.append(bezier(net))
    np.testing.assert_allclose(sources[0].evaluate_grid([.25],[0]),sources[0].evaluate_grid([.75],[0]),atol=1e-14)
    r=check(*sources,max_depth=6,max_charts=127,max_pairs=4096)
    assert r['partition_report']['all_leaves_numeric_injective']
    assert not r['numeric_injective'] and r['status']=='UNRESOLVED'
    assert any(p['reason']=='hulls_not_separated' and p['second_leaf']>p['first_leaf']+1 for p in r['pair_records'])


def test_adjacent_charts_need_far_parts_checked_even_when_the_collar_is_injective():
    # A closed loop C(0)=C(1), regular and injective on each half. The middle
    # collar is injective, but the far endpoints of the two halves coincide.
    xy=np.array([[0,0],[2,-1],[2,1],[0,0]])
    sources=[]
    for sign in (-1,1):
        net=np.empty((4,2,3));net[:,:,:2]=xy[:,None];net[:,:,2]=[0,sign]
        sources.append(bezier(net))
    r=check(*sources)
    assert r['partition_report']['all_leaves_numeric_injective'] and r['required_pairs']==1
    pair=r['pair_records'][0]
    assert pair['collar_report']['numeric_injective'] and len(pair['separations'])==2
    assert pair['reason']=='hulls_not_separated' and not r['numeric_injective']


def test_wide_unresolved_collar_is_not_replaced_by_separate_leaf_successes():
    r=check(*shear(),collar_fraction=.99)
    assert r['partition_report']['all_leaves_numeric_injective'] and not r['numeric_injective']
    assert any(p['reason']=='collar_condition_unmet' for p in r['pair_records'])


@pytest.mark.parametrize('limit',[1,5])
def test_pair_limit_is_checked_before_partial_pair_results(limit):
    r=check(*shear(),max_pairs=limit)
    assert r['status']=='RESOURCE_LIMIT' and r['reason']=='max_pairs' and r['required_pairs']==6
    assert not r['pair_records'] and not r['numeric_injective'] and not r['pair_scan_complete']


def test_unresolved_leaf_or_gap_never_enters_the_union_pass_path():
    a,b=shear();r=check(a,b,max_depth=0)
    assert not r['numeric_injective'] and r['reason']=='leaf_conditions_unmet' and not r['pair_records']
    b.across.c[:,:,2]+=1e-15;r=check(a,b)
    assert not r['numeric_injective'] and not r['cross_chart_pairs_checked']


def test_partition_resource_failure_is_retained():
    r=check(*shear(),max_charts=1)
    assert r['status']=='RESOURCE_LIMIT' and not r['numeric_injective']


def test_strict_far_separation_budget_is_not_relaxed_to_accept_equality():
    r=check(*shear(),nonadjacent_clearance_mm=.25)
    assert not r['numeric_injective']
    assert any(s['projection_lower_mm']<=.25 and not s['numeric_separated']
               for p in r['pair_records'] for s in p['separations'])


@pytest.mark.parametrize('scale',[.1,10.])
def test_shear_after_rigid_transform_and_scale_still_has_complete_pair_coverage(scale):
    a,b=shear();q,_=np.linalg.qr(np.array([[1.,2,3],[-2,3,1],[3,1,-2]]))
    for s in (a,b):s.across.c=s.across.c@q*scale+[10,-20,30]
    r=check(a,b)
    assert r['numeric_injective'] and r['pair_scan_complete']


@pytest.mark.parametrize('options',[{'collar_fraction':0},{'collar_fraction':1},{'collar_fraction':True},
    {'collar_fraction':float('nan')},{'max_pairs':0},{'max_pairs':True},
    {'nonadjacent_clearance_mm':-1},{'nonadjacent_clearance_mm':True}])
def test_invalid_union_options_are_rejected(options):
    with pytest.raises(ValueError):check(*shear(),**options)


@pytest.mark.parametrize('bounds',[(0.,1.),(.15,.85),(.25,.5)])
def test_restricted_hull_contains_dense_original_surface_across_internal_knots(bounds):
    source=patch(lambda s,t:np.column_stack((t+2*s*s,0*t+s,t*t-3*s*t)),9,(0.,.2,.5,.8,1.))
    poles=_hull_points(source,bounds,(.1,.9));q,_=np.linalg.qr(np.array([[1.,2,3],[-2,3,1],[3,1,-2]]))
    projected=poles@q
    actual=source.evaluate_grid(np.linspace(*bounds,41),np.linspace(.1,.9,43))@q
    assert np.all(actual>=projected.min(axis=0)-1e-12) and np.all(actual<=projected.max(axis=0)+1e-12)


def test_source_candidate_binding_is_opt_in_and_preserves_the_prior_report():
    source,envelope=fixture();before=deepcopy(envelope)
    r=local_seam_union_injectivity(source,envelope,1,2,reference_min_mm=1e-12,monotonic_margin=0,
                                  nonadjacent_clearance_mm=0,projection_strategy='balanced_transverse')
    assert r['expected_parameter_contact_only'] and r['source_identity_checked'] and r['mapping_identity_checked']
    assert r['candidate_report']['query_faces']==[1,2]
    assert r['candidate_report']['expected_parameter_contact_only']
    assert envelope['status']==before['status'] and envelope['mapping_fingerprint']==before['mapping_fingerprint']
    for k in envelope['mesh']:np.testing.assert_array_equal(envelope['mesh'][k],before['mesh'][k])
    source['ps'].across.c[1,1,0]+=.01
    with pytest.raises(ValueError,match='Source surface changed'):
        local_seam_union_injectivity(source,envelope,1,2,reference_min_mm=1e-12,monotonic_margin=0,nonadjacent_clearance_mm=0)


@pytest.mark.parametrize('ends',[(0,0),(0,-1),(-1,0),(-1,-1)])
def test_partial_width_source_hulls_and_signed_chart_ends_cover_the_same_union(ends):
    a,b=shear()
    for source,end in zip((a,b),ends):
        if end==-1:source.across.c=source.across.c[:,::-1].copy()
    r=seam_union_injectivity(a,ends[0],b,ends[1],first_width=.7,second_width=.4,
        reference_min_mm=1e-12,monotonic_margin=0,nonadjacent_clearance_mm=0)
    assert r['numeric_injective'] and r['cross_chart_pairs_checked']
    assert r['partition_report']['root_report']['widths']==[.7,.4]


def test_candidate_with_unresolved_local_leaves_is_not_promoted():
    source={}
    for role,g in tube(2,2).items():
        net=np.stack((g[0],(g[0]+g[1])/2,g[1]));net[-1,:,0]+=100
        source[role]=bezier(net)
    envelope=merged_role_error_envelope(source,target_mm=100,join_tolerance_mm=1e-8)
    r=local_seam_union_injectivity(source,envelope,1,2,reference_min_mm=1e-12,monotonic_margin=0,
                                  nonadjacent_clearance_mm=0)
    assert not r['union_report']['partition_report']['all_leaves_numeric_injective']
    assert not r['expected_parameter_contact_only'] and not r['candidate_report']['expected_parameter_contact_only']


def test_candidate_union_can_pass_without_rewriting_the_old_root_only_result():
    # Split one straight contour edge into two roles, then extrude with exactly
    # the analytic shear used above. Other roles close the diagnostic contour.
    contour={'le':((-1,0),(0,0)),'ps':((0,0),(1,0)),
             'te':((1,0),(0,1)),'ss':((-1,0),(0,1))}
    source={}
    for role,points in contour.items():
        net=np.empty((3,2,3));net[:,:,:2]=points;net[:,:,2]=np.array([0,.5,1])[:,None]
        net[-1,:,0]+=10;source[role]=bezier(net)
    envelope=merged_role_error_envelope(source,target_mm=100,join_tolerance_mm=1e-8)
    r=local_seam_union_injectivity(source,envelope,1,2,reference_min_mm=1e-12,monotonic_margin=0,
                                  nonadjacent_clearance_mm=0)
    assert r['expected_parameter_contact_only'] and r['union_report']['cross_chart_pairs_checked']
    assert not r['candidate_report']['expected_parameter_contact_only']
    assert r['candidate_report']['status']=='LOCAL_CHARTS_ONLY'
