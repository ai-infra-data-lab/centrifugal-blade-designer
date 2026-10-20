"""Parent-cell coverage, identity protection and non-gluing of local successes."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.seam_contact_refinement import (
    subdivide_seam_neighborhood,local_seam_pair_injectivity)
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
from blade_designer.geometry.contact_sources import mapping_fingerprint
from test_seam_injectivity import strips,bezier
from test_role_seams import tube


def check(a,b,**options):
    return subdivide_seam_neighborhood(a,0,b,0,**{'first_width':1.,'second_width':1.,
        'reference_min_mm':1e-12,'monotonic_margin':0.,**options})


def shear():
    result=[]
    for sign in (-1,1):
        result.append(bezier([[[0,0,0],[sign,0,0]],[[0,.5,0],[sign,.5,0]],
                              [[10,1,0],[10+sign,1,0]]]))
    return result


def fixture():
    source={r:bezier(g) for r,g in tube(2,2).items()}
    envelope=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=1e-8)
    return source,envelope


def pair(source,envelope,a=1,b=2,**options):
    return local_seam_pair_injectivity(source,envelope,a,b,
        **{'reference_min_mm':1e-12,'monotonic_margin':0.,**options})


def test_positive_root_stops_without_unnecessary_subdivision():
    a,b=strips();before=deepcopy((a.across.c,b.across.c))
    r=check(a,b)
    assert r['numeric_injective'] and r['chart_count']==1 and r['leaf_indices']==[0]
    assert r['all_leaves_numeric_injective'] and not r['stop_reasons']
    assert not r['whole_geometry_verified'] and not r['roundoff_certified']
    for s,old in zip((a,b),before):np.testing.assert_array_equal(s.across.c,old)


def test_successful_children_with_different_projections_do_not_prove_union():
    r=check(*shear(),max_depth=3)
    assert r['status']=='LOCAL_CHARTS_ONLY' and not r['numeric_injective']
    assert not r['root_report']['numeric_injective'] and r['all_leaves_numeric_injective']
    assert r['chart_count']==7 and not r['cross_chart_pairs_checked']
    intervals=[r['charts'][i]['report']['span_range'] for i in r['leaf_indices']]
    assert sorted(intervals)==[[0,.25],[.25,.5],[.5,.75],[.75,1]]
    projections=[r['charts'][i]['report']['projection'] for i in r['leaf_indices']]
    assert not np.allclose(projections[0],projections[-1])
    for node in r['charts']:
        if node['children']:
            left,right=[r['charts'][i] for i in node['children']]
            assert left['report']['span_range'][0]==node['report']['span_range'][0]
            assert right['report']['span_range'][1]==node['report']['span_range'][1]
            assert left['report']['span_range'][1]==right['report']['span_range'][0]
        assert node['report']['widths']==[1.,1.]


@pytest.mark.parametrize('limit',[1,2,3,4,5,6])
def test_total_chart_limit_preserves_unresolved_leaves_and_never_claims_success(limit):
    r=check(*shear(),max_charts=limit)
    assert r['status']=='RESOURCE_LIMIT' and not r['numeric_injective']
    assert r['chart_count']<=limit and r['stop_reasons']['max_charts']>0
    assert not r['all_leaves_numeric_injective']
    leaves=sorted(r['charts'][i]['report']['span_range'] for i in r['leaf_indices'])
    assert leaves[0][0]==0 and leaves[-1][1]==1
    assert all(a[1]==b[0] for a,b in zip(leaves,leaves[1:]))


def test_depth_and_per_chart_cell_limits_are_distinct():
    depth=check(*shear(),max_depth=0)
    assert depth['status']=='UNRESOLVED' and depth['stop_reasons']=={'max_depth':1}
    cells=check(*strips(),max_cells=1)
    assert cells['status']=='RESOURCE_LIMIT' and cells['chart_count']==1
    assert cells['stop_reasons']=={'max_cells':1} and not cells['numeric_injective']


def test_gap_mismatch_is_not_subdivided_or_repaired():
    a,b=strips();b.across.c[:,:,2]+=1e-15
    r=check(a,b)
    assert r['status']=='UNRESOLVED' and r['chart_count']==1
    assert r['stop_reasons']=={'boundary_representation_mismatch':1}
    assert not r['coordinates_modified']


@pytest.mark.parametrize('options',[{'max_depth':-1},{'max_depth':True},{'max_depth':9},
    {'max_charts':0},{'max_charts':True},{'first_width':0},{'max_cells':False},
    {'span_range':(1,0)},{'monotonic_margin':float('nan')}])
def test_invalid_adaptive_options(options):
    with pytest.raises(ValueError):check(*strips(),**options)


@pytest.mark.parametrize('faces',[(1,2),(2,1),(0,6),(6,0),(4,2),(5,7)])
def test_declared_candidates_bind_original_sources_and_cover_both_parent_cells(faces):
    source,envelope=fixture();before=deepcopy(envelope);net={r:s.across.c.copy() for r,s in source.items()}
    r=pair(source,envelope,*faces)
    assert r['expected_parameter_contact_only'] and r['source_identity_checked'] and r['mapping_identity_checked']
    assert r['query_faces']==list(faces) and r['enclosing_parent_cells']
    chart=r['neighborhood_report']['root_report']
    assert chart['span_range']==[0,1] and chart['widths']==[1,1]
    assert not r['whole_geometry_verified'] and not r['continuous_surface_certified']
    assert envelope['status']==before['status'] and envelope['mapping_fingerprint']==before['mapping_fingerprint']
    for key in envelope['mesh']:np.testing.assert_array_equal(envelope['mesh'][key],before['mesh'][key])
    for role,s in source.items():np.testing.assert_array_equal(s.across.c,net[role])


def test_stale_sources_and_missing_identity_are_rejected():
    source,envelope=fixture();source['ps'].across.c[1,1,0]+=.01
    with pytest.raises(ValueError,match='Source surface changed'):pair(source,envelope)
    source,envelope=fixture();del envelope['source_fingerprints']['ps']
    with pytest.raises(ValueError,match='Source surface changed'):pair(source,envelope)


def test_mutated_mapping_and_old_report_are_rejected():
    source,envelope=fixture();envelope['mesh']['faces'][1,0]+=1
    with pytest.raises(ValueError,match='mapping'):pair(source,envelope)
    source,envelope=fixture();del envelope['mapping_fingerprint']
    with pytest.raises(ValueError,match='mapping'):pair(source,envelope)


@pytest.mark.parametrize('faces',[(0,0),(0,1),(0,4),(-1,2),(True,2),(1,99)])
def test_invalid_candidate_queries_are_rejected(faces):
    source,envelope=fixture()
    with pytest.raises(ValueError):pair(source,envelope,*faces)


def test_forged_shared_id_does_not_accept_an_interior_cell_as_a_seam():
    source,envelope=fixture()
    # Deliberately synthesize a fresh mapping snapshot with le no longer reaching xi=1.
    # This is not a stale-ID case: the additional seam-domain condition is essential.
    envelope['alignment']['role_coordinates']['le'][-1]=.8
    envelope['mapping_fingerprint']=mapping_fingerprint(envelope)
    with pytest.raises(ValueError,match='does not touch'):pair(source,envelope)


def test_candidate_children_cannot_override_unresolved_parent_contact():
    source={}
    for role,g in tube(2,2).items():
        net=np.stack((g[0],(g[0]+g[1])/2,g[1]))
        net[-1,:,0]+=100
        source[role]=bezier(net)
    envelope=merged_role_error_envelope(source,target_mm=100,join_tolerance_mm=1e-8)
    r=pair(source,envelope,max_depth=4)
    assert not r['neighborhood_report']['root_report']['numeric_injective']
    assert not r['expected_parameter_contact_only'] and not r['whole_geometry_verified']
    assert envelope['status']=='NUMERIC_TARGET_MET'
