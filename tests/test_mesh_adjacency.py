"""Analytic shared-edge joins, folded neighbors and incomplete topology."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.mesh_contacts import mesh_contacts, grid_mesh
from blade_designer.geometry.blade_contacts import screen_blade_grids, ROLES


FACES=np.array([[0,1,2],[1,0,3]])


def pair(third):
    return np.array([[0.,0.,0.],[2.,0.,0.],[0.,2.,0.],third])


def check(v,faces=FACES,**kwargs):
    return mesh_contacts(v,faces,tolerance_mm=kwargs.pop('tolerance_mm',1e-10),
                         area_epsilon_mm2=0,check_shared_edges=True,**kwargs)


@pytest.mark.parametrize('third,contact',[
    ([0.,-2.,0.],False),([0.,0.,2.],False),([.5,.5,1.],False),
    ([.5,.5,0.],True),([0.,2.,0.],True),([0.,4.,0.],True),
])
def test_expected_edge_joins_and_positive_area_overlap_are_distinct(third,contact):
    v=pair(third);before=deepcopy((v,FACES))
    r=check(v)
    assert bool(r['contact_count']) is contact and r['scan_complete']
    assert r['adjacency']['checked_shared_edge_pairs']==1
    assert r['adjacency']['expected_shared_edge_pairs']==int(not contact)
    assert r['adjacency']['overlap_candidates']==int(contact)
    assert r['adjacency']['nonmanifold_edge_count']==0
    if contact:assert r['contact_kinds']==['shared_edge_overlap_candidate']
    for x,y in zip(before,(v,FACES)):np.testing.assert_array_equal(x,y)


@pytest.mark.parametrize('scale',[.01,1.,100.])
@pytest.mark.parametrize('contact',[False,True])
def test_isometry_scale_and_face_winding_do_not_define_overlap(scale,contact):
    q,_=np.linalg.qr(np.array([[1.,2.,3.],[-2.,3.,1.],[3.,1.,-2.]]))
    v=scale*pair([.5,.5,0.] if contact else [0.,-2.,0.])@q+[20.,-30.,50.]
    for faces in (FACES,FACES[::-1],FACES[:,::-1],np.array([[2,0,1],[3,1,0]])):
        r=check(v,faces,tolerance_mm=1e-10*scale)
        assert bool(r['contact_count']) is contact and r['scan_complete']


@pytest.mark.parametrize('height,contact',[(1e-8,True),(1e-4,False)])
def test_near_coplanar_tolerance_band_is_a_candidate_not_actual_intersection(height,contact):
    # Both are noncoplanar in exact arithmetic and meet only along the edge.
    r=check(pair([.5,.5,height]),tolerance_mm=1e-6)
    assert bool(r['contact_count']) is contact and r['scan_complete']
    assert r['roundoff_certified'] is False


def test_legacy_default_keeps_old_exclusion_and_opt_in_detects_its_known_fold():
    v=pair([.5,.5,0.])
    old=mesh_contacts(v,FACES,tolerance_mm=1e-10,area_epsilon_mm2=0)
    assert old['adjacent_pairs_excluded']==1 and old['contact_count']==0
    assert not old['adjacency']['enabled'] and old['adjacency']['nonmanifold_edge_count'] is None
    new=check(v)
    assert new['contact_pairs']==[[0,1]] and new['adjacent_pairs_excluded']==0


@pytest.mark.parametrize('short_edge',[False,True])
def test_short_edge_or_height_is_unresolved_not_expected_or_a_clean_scan(short_edge):
    v=pair([.5,1e-8,0.])
    if short_edge:v[1]=[1e-8,0,0]
    r=check(v,tolerance_mm=1e-7)
    assert r['status']=='INCOMPLETE' and not r['scan_complete']
    assert r['contact_count']==0 and r['adjacency']['unresolved_count']==1
    assert r['adjacency']['unresolved_examples']==[[0,1]]


def test_nonmanifold_three_face_edge_is_incomplete_even_without_overlap():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],
                [0.,-.5,np.sqrt(.75)],[0.,-.5,-np.sqrt(.75)]])
    f=np.array([[0,1,2],[1,0,3],[0,1,4]])
    r=check(v,f)
    assert r['contact_count']==0 and r['adjacency']['expected_shared_edge_pairs']==3
    assert r['status']=='INCOMPLETE' and r['adjacency']['nonmanifold_edge_count']==1
    assert r['adjacency']['nonmanifold_edge_examples']==[{'edge':[0,1],'face_count':3,'face_examples':[0,1,2]}]


def test_unresolved_and_incidence_examples_are_bounded_without_hiding_total():
    v=np.array([[0.,0.,0.],[1e-8,0.,0.],[0.,1.,0.],[0.,0.,1.],[0.,-1.,0.]])
    f=np.array([[0,1,2],[1,0,3],[0,1,4]])
    r=check(v,f,tolerance_mm=1e-7,max_contacts=1)
    assert r['adjacency']['unresolved_count']==3
    assert len(r['adjacency']['unresolved_examples'])==1 and r['adjacency']['unresolved_examples_truncated']
    assert r['adjacency']['nonmanifold_edge_examples'][0]['face_count']==3
    assert len(r['adjacency']['nonmanifold_edge_examples'][0]['face_examples'])==1
    assert not r['scan_complete']


def test_bvh_grid_shared_edges_are_checked_once_and_vertex_neighbors_stay_explicit():
    grid=np.array([[[x,y,0.] for y in range(5)] for x in range(3)])
    v,f=grid_mesh(grid);r=check(v,f)
    # 8 diagonal + 6 one-direction + 4 other-direction interior edges.
    assert r['adjacency']['checked_shared_edge_pairs']==18
    assert r['adjacency']['expected_shared_edge_pairs']==18
    assert r['adjacency']['vertex_neighbor_pairs_excluded']>0
    assert r['adjacent_pairs_excluded']==r['adjacency']['vertex_neighbor_pairs_excluded']
    assert r['adjacency']['vertex_links_checked'] is False
    assert r['contact_count']==0 and r['scan_complete']


def test_degenerate_faces_are_not_used_to_invent_edge_incidence():
    r=check(pair([0.,-2.,0.]),np.array([[0,1,2],[0,1,0],[0,1,0]]))
    assert r['first_degenerate_faces']==[1,2]
    assert r['adjacency']['nonmanifold_edge_count']==0 and not r['scan_complete']


@pytest.mark.parametrize('limit,reason',[({'max_work':1},'max_work'),({'max_contacts':1},'max_contacts')])
def test_local_candidate_limits_remain_incomplete(limit,reason):
    r=check(pair([.5,.5,0.]),**limit)
    assert not r['scan_complete'] and r['stop_reason']==reason
    assert r['status']!='NO_CONTACT_OBSERVED'


@pytest.mark.parametrize('value',[1,None,np.bool_(True)])
def test_non_bool_options_rejected_at_both_entry_points(value):
    with pytest.raises(ValueError,match='check_shared_edges'):
        mesh_contacts(pair([.5,.5,0.]),FACES,tolerance_mm=0,area_epsilon_mm2=0,check_shared_edges=value)
    with pytest.raises(ValueError,match='check_shared_edges'):
        screen_blade_grids({},1,tolerance_mm=0,area_epsilon_mm2=0,check_shared_edges=value)


def test_separate_mesh_vertex_numbers_do_not_imply_shared_topology():
    v=pair([.5,.5,0.])
    with pytest.raises(ValueError,match='self check'):
        mesh_contacts(v,FACES,v,FACES,tolerance_mm=0,area_epsilon_mm2=0,check_shared_edges=True)


@pytest.mark.parametrize('folded',[False,True])
def test_role_self_checks_opt_in_and_propagate_the_scope_without_changing_grids(folded):
    grid=np.array([[[0.,0.,0.],[2.,0.,0.]],[[0.,2.,0.],[2.,2.,0.]]])
    if folded:grid=np.array([[[0.,0.,0.],[1.5,.5,0.]],[[2.,0.,0.],[2.,2.,0.]]])
    grids={r:grid+[0,0,10*i] for i,r in enumerate(ROLES)};before=deepcopy(grids)
    old=screen_blade_grids(grids,1,tolerance_mm=1e-10,area_epsilon_mm2=0)
    new=screen_blade_grids(grids,1,tolerance_mm=1e-10,area_epsilon_mm2=0,check_shared_edges=True)
    assert old['contact_count']==0 and new['contact_count']==(4 if folded else 0)
    assert new['scan_complete'] and new['check_shared_edges']
    assert new['unchecked'][0]=='vertex-only neighbors and vertex links within a role'
    for r in ROLES:np.testing.assert_array_equal(grids[r],before[r])


def test_periodic_checks_do_not_misuse_shared_vertex_ids():
    grid=np.array([[[20.,0.,0.],[21.,0.,0.]],[[20.,1.,0.],[21.,1.,0.]]])
    grids={r:grid+[0,0,10*i] for i,r in enumerate(ROLES)}
    r=screen_blade_grids(grids,20,tolerance_mm=1e-10,area_epsilon_mm2=0,check_shared_edges=True)
    assert r['check_count']==20
    assert all(c['report']['adjacency']['enabled']==(c['second_group'] is None) for c in r['checks'])


def test_role_unresolved_edges_propagate_incomplete_without_becoming_contacts():
    grid=np.array([[[0.,0.,0.],[2.,0.,0.]],[[0.,1e-8,0.],[2.,1e-8,0.]]])
    grids={r:grid+[0,0,10*i] for i,r in enumerate(ROLES)}
    result=screen_blade_grids(grids,1,tolerance_mm=1e-7,area_epsilon_mm2=0,check_shared_edges=True)
    assert result['contact_count']==0 and result['incomplete_checks']==4
    assert result['status']=='INCOMPLETE' and not result['scan_complete']


def test_duplicate_face_contact_is_not_filtered_by_new_edge_classifier():
    r=check(pair([0.,-2.,0.]),np.array([[0,1,2],[2,1,0]]))
    assert r['contact_pairs']==[[0,1]] and r['contact_kinds']==['triangle_contact_candidate']
    assert r['adjacency']['checked_shared_edge_pairs']==0
