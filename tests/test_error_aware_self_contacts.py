"""Local position uncertainty never hides folds or nonlocal mesh candidates."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.error_aware_self_contacts import error_aware_self_contacts
from blade_designer.geometry.mesh_contacts import grid_mesh,mesh_contacts
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
from test_conforming_role_grids import surfaces


def check(v,f,error=0.,**options):
    return error_aware_self_contacts(v,f,np.full(len(f),error),
                                    **{'clearance_mm':0.,'adjacency_tolerance_mm':1e-10,
                                       'area_epsilon_mm2':0.,**options})


def grid():
    x,y=np.meshgrid(np.arange(5.),np.arange(3.))
    return grid_mesh(np.stack((x,y,np.zeros_like(x)),axis=-1))


def test_exact_planar_grid_has_expected_shared_edges_vertices_and_valid_links():
    v,f=grid();r=check(v,f)
    assert r['status']=='NUMERIC_NO_UNEXPECTED_CONTACT' and r['scan_complete']
    assert r['expected_edge_pairs']==18 and r['expected_vertex_pairs']==35
    assert r['nonlocal_numeric_separated'] and not r['issue_pairs']
    assert not r['whole_geometry_verified'] and not r['continuous_surface_certified']


def test_positive_error_keeps_source_neighborhood_uncertain_without_stopping_scan():
    v,f=grid();r=check(v,f,.01,max_examples=1)
    assert r['status']=='UNCERTAIN' and r['scan_complete'] and r['nonlocal_numeric_separated']
    assert r['local_error_uncertain_pairs']==53 and r['issue_pairs']==53
    assert len(r['examples'])==1 and r['examples_truncated'] and r['stop_reason'] is None
    assert not r['numeric_no_unexpected_contact']


@pytest.mark.parametrize('third,fold',[([0,-2,0],False),([0,0,2],False),([.5,.5,0],True)])
@pytest.mark.parametrize('error',[0.,.01])
def test_expected_edge_and_fold_with_and_without_source_error(third,fold,error):
    v=np.array([[0.,0,0],[2,0,0],[0,2,0],third]);f=np.array([[0,1,2],[1,0,3]])
    r=check(v,f,error)
    assert bool(r['local_contact_candidates'])==fold
    assert r['status']==('CONTACT_CANDIDATES_FOUND' if fold else 'UNCERTAIN' if error else 'NUMERIC_NO_UNEXPECTED_CONTACT')


def test_shared_vertex_fold_and_disconnected_link_are_both_reported():
    v=np.array([[0.,0,0],[2,0,0],[0,2,0],[1,1,1],[1,1,-1]])
    r=check(v,np.array([[0,1,2],[0,3,4]]),.01)
    assert r['local_contact_candidates']==1 and r['nonmanifold_vertex_count']==1
    assert r['pair_scan_complete'] and not r['scan_complete']


def test_local_error_examples_do_not_hide_later_nonlocal_crossing():
    v,f=grid()
    # Last two independent triangles cross well away from the planar grid.
    extra=np.array([[10.,0,0],[12,0,0],[10,2,0],[10.5,.5,-1],[10.5,.5,1],[11.5,.5,0]])
    f=np.concatenate((f,np.arange(len(v),len(v)+6).reshape(2,3)));v=np.concatenate((v,extra))
    r=check(v,f,.01,max_examples=1)
    assert r['local_error_uncertain_pairs']>0 and r['nonlocal_contact_candidates']==1
    assert r['status']=='CONTACT_CANDIDATES_FOUND' and r['scan_complete']
    assert r['examples_truncated'] and not r['nonlocal_numeric_separated']


def test_near_disjoint_faces_use_error_sum_and_clearance():
    a=np.array([[0.,0,0],[2,0,0],[0,2,0]]);v=np.concatenate((a,a+[0,0,.2]));f=np.arange(6).reshape(2,3)
    assert check(v,f,.05)['nonlocal_numeric_separated']
    assert check(v,f,.05,clearance_mm=.1)['status']=='UNCERTAIN'
    assert check(v,f,.11)['nonlocal_uncertain_pairs']==1


def test_coordinate_coincidence_does_not_weld_distinct_vertex_ids():
    a=np.array([[0.,0,0],[2,0,0],[0,2,0]])
    r=check(np.concatenate((a,a)),np.arange(6).reshape(2,3))
    assert r['nonlocal_contact_candidates']==1 and r['expected_edge_pairs']==0


def test_duplicate_faces_have_local_candidate_and_invalid_links():
    v=np.array([[0.,0,0],[2,0,0],[0,2,0]])
    r=check(v,np.array([[0,1,2],[0,1,2]]))
    assert r['local_contact_candidates']==1 and not r['scan_complete']
    assert r['nonmanifold_vertex_count']==3


def test_nonmanifold_three_face_edge_is_not_a_complete_clean_result():
    v=np.array([[0.,0,0],[1,0,0],[0,1,0],[0,-.5,.866],[0,-.5,-.866]])
    r=check(v,np.array([[0,1,2],[1,0,3],[0,1,4]]))
    assert r['nonmanifold_edge_count']==1 and not r['scan_complete']
    assert not r['numeric_no_unexpected_contact']


def test_degenerate_and_work_limit_are_incomplete():
    v,f=grid()
    r=check(v,f,max_work=1)
    assert r['status']=='INCOMPLETE' and not r['nonlocal_numeric_separated']
    assert r['stop_reason']=='max_work'
    f[0]=[0,0,1];r=check(v,f)
    assert r['degenerate_faces']==[0] and not r['scan_complete']


def test_short_local_height_is_relation_unresolved_not_source_uncertainty():
    v=np.array([[0.,0,0],[2,0,0],[0,2,0],[.5,1e-8,0]])
    r=check(v,np.array([[0,1,2],[1,0,3]]),adjacency_tolerance_mm=1e-7)
    assert r['local_relation_unresolved_pairs']==1 and r['local_error_uncertain_pairs']==0
    assert r['status']=='INCOMPLETE'


@pytest.mark.parametrize('options',[{'clearance_mm':True},{'adjacency_tolerance_mm':-1},
                                   {'area_epsilon_mm2':np.inf},{'max_work':0},{'max_examples':False},{'max_triangles':0}])
def test_invalid_options_rejected(options):
    v,f=grid()
    with pytest.raises(ValueError):check(v,f,**options)


@pytest.mark.parametrize('bad',[[-1],[np.nan],[True],0])
def test_invalid_error_vector_rejected(bad):
    v,f=grid()
    with pytest.raises(ValueError):
        error_aware_self_contacts(v,f,bad,clearance_mm=0,adjacency_tolerance_mm=0,area_epsilon_mm2=0)


@pytest.mark.parametrize('scale',[.01,1.,100.])
def test_transform_winding_and_scale_preserve_diagnosis(scale):
    v,f=grid();q,_=np.linalg.qr(np.array([[1.,2,3],[-2,3,1],[3,1,-2]]))
    v=v@q*scale+[20,-30,50]
    for faces in (f,f[:,::-1],f[::-1]):
        r=check(v,faces,.01*scale,adjacency_tolerance_mm=1e-10*scale)
        assert r['status']=='UNCERTAIN' and r['local_error_uncertain_pairs']==53


def test_merged_role_mesh_preserves_inputs_and_old_triangle_relations():
    result=merged_role_error_envelope(surfaces(),target_mm=.03,join_tolerance_mm=1e-8)
    m=result['mesh'];before=deepcopy((m['vertices'],m['faces'],result['merged_triangle_upper_mm']))
    r=error_aware_self_contacts(*before,clearance_mm=0,adjacency_tolerance_mm=1e-10,area_epsilon_mm2=0)
    old=mesh_contacts(before[0],before[1],tolerance_mm=1e-10,area_epsilon_mm2=0,
                      check_shared_edges=True,check_shared_vertices=True)
    assert r['expected_edge_pairs']==old['adjacency']['expected_shared_edge_pairs']
    assert r['expected_vertex_pairs']==old['vertex_adjacency']['expected_vertex_pairs']
    assert not r['local_contact_candidates'] and r['nonlocal_numeric_separated']
    for a,b in zip(before,(m['vertices'],m['faces'],result['merged_triangle_upper_mm'])):np.testing.assert_array_equal(a,b)


def test_per_triangle_error_only_marks_incident_local_pairs():
    v,f=grid();errors=np.zeros(len(f));errors[0]=.01
    r=error_aware_self_contacts(v,f,errors,clearance_mm=0,adjacency_tolerance_mm=1e-10,area_epsilon_mm2=0)
    expected=sum(bool(set(f[0])&set(face)) for face in f[1:])
    assert r['local_error_uncertain_pairs']==expected and expected<53
    assert r['nonlocal_numeric_separated']


def test_single_triangle_is_not_compared_with_itself():
    v=np.array([[0.,0,0],[2,0,0],[0,2,0]])
    r=check(v,np.array([[0,1,2]]),.1)
    assert r['triangle_pair_tests']==0 and not r['issue_pairs']
    assert r['numeric_no_unexpected_contact'] and not r['whole_geometry_verified']


def test_overflow_does_not_produce_clean_status():
    v,f=grid()
    with pytest.raises(ValueError):check(v,f,1e308,clearance_mm=1e308)
