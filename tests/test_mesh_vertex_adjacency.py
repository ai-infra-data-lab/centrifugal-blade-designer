"""Analytic cone intersections and vertex links, independent of CAD fixtures."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.mesh_contacts import mesh_contacts, grid_mesh
from blade_designer.geometry.blade_contacts import screen_blade_grids, ROLES

FACES=np.array([[0,1,2],[0,3,4]])

def pair(b):
    return np.array([[0.,0.,0.],[2.,0.,0.],[0.,2.,0.],*b])

def check(v,faces=FACES,**kwargs):
    return mesh_contacts(v,faces,tolerance_mm=kwargs.pop('tolerance_mm',1e-10),
                         area_epsilon_mm2=0,check_shared_edges=True,check_shared_vertices=True,**kwargs)

@pytest.mark.parametrize('b,contact',[
    ([[1,1,1],[1,1,-1]],True),([[-1,-1,1],[-1,-1,-1]],False),
    ([[-1,0,0],[0,-1,0]],False),([[1,1,0],[0,2,0]],True),
    ([[2,0,0],[1,-1,0]],True),([[-2,0,0],[0,2,0]],True),
    ([[1,-1,0],[-1,-1,0]],False),
])
def test_ray_intersection_beyond_shared_vertex(b,contact):
    v=pair(b);before=deepcopy((v,FACES));r=check(v);a=r['vertex_adjacency']
    assert bool(r['contact_count']) is contact
    assert a['checked_vertex_pairs']==1 and a['expected_vertex_pairs']==int(not contact)
    assert a['overlap_candidates']==int(contact) and a['unresolved_count']==0
    # Two independent fans at one vertex are topologically disconnected even
    # when their geometric intersection is only the shared point.
    assert a['nonmanifold_vertex_count']==1 and not r['scan_complete']
    if contact:assert r['contact_kinds']==['shared_vertex_overlap_candidate']
    for x,y in zip(before,(v,FACES)):np.testing.assert_array_equal(x,y)

@pytest.mark.parametrize('scale',[.01,1.,100.])
@pytest.mark.parametrize('contact',[False,True])
def test_rotation_translation_scale_and_winding(scale,contact):
    q,_=np.linalg.qr(np.array([[1.,2.,3.],[-2.,3.,1.],[3.,1.,-2.]]))
    b=[[1,1,1],[1,1,-1]] if contact else [[-1,-1,1],[-1,-1,-1]]
    v=scale*pair(b)@q+[20.,-30.,50.]
    for faces in (FACES,FACES[::-1],FACES[:,::-1]):
        r=check(v,faces,tolerance_mm=1e-10*scale)
        assert bool(r['contact_count']) is contact
        assert r['vertex_adjacency']['unresolved_count']==0

@pytest.mark.parametrize('edge_mode',[False,True])
def test_previous_modes_still_exclude_vertex_fold(edge_mode):
    r=mesh_contacts(pair([[1,1,1],[1,1,-1]]),FACES,tolerance_mm=1e-10,
                    area_epsilon_mm2=0,check_shared_edges=edge_mode)
    assert r['contact_count']==0 and r['adjacent_pairs_excluded']==1 and r['scan_complete']
    assert r['adjacency']['vertex_neighbor_pairs_excluded']==1
    assert not r['adjacency']['vertex_links_checked']
    assert r['vertex_adjacency']['nonmanifold_vertex_count'] is None

def test_regular_grid_has_path_and_cycle_links_and_all_neighbors_checked():
    x,y=np.meshgrid(np.arange(5.),np.arange(3.))
    v,f=grid_mesh(np.stack((x,y,np.zeros_like(x)),axis=-1));r=check(v,f)
    assert r['contact_count']==0 and r['scan_complete']
    assert r['adjacency']['expected_shared_edge_pairs']==18
    assert r['vertex_adjacency']['expected_vertex_pairs']==35
    assert r['vertex_adjacency']['nonmanifold_vertex_count']==0
    assert r['adjacent_pairs_excluded']==0 and r['adjacency']['vertex_links_checked']

def test_closed_tetrahedron_has_cycle_links():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    r=check(v,np.array([[0,1,2],[0,3,1],[0,2,3],[1,3,2]]))
    assert r['scan_complete'] and r['vertex_adjacency']['nonmanifold_vertex_count']==0

def test_duplicate_faces_are_not_simple_links_and_examples_are_bounded():
    r=check(pair([[1,1,1],[1,1,-1]]),np.array([[0,1,2],[0,1,2]]),max_contacts=1)
    a=r['vertex_adjacency']
    assert a['nonmanifold_vertex_count']==3 and len(a['nonmanifold_vertex_examples'])==1
    assert a['nonmanifold_vertex_examples'][0]['duplicate_link_edges']==1
    assert r['contact_count']==1 and not r['scan_complete']

def test_short_altitude_is_unresolved_not_clear():
    r=check(pair([[1.,0.,0.],[1.,1e-8,0.]]),tolerance_mm=1e-6)
    assert r['vertex_adjacency']['unresolved_count']==1 and not r['scan_complete']

def test_tiny_intersection_segment_is_unresolved():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[-1.,1.5e-7,0.],[-.1,1.,0.],[.1,1.,0.]])
    r=check(v,tolerance_mm=1e-7)
    assert r['vertex_adjacency']['unresolved_count']==1 and r['contact_count']==0

def test_near_coplanar_projection_is_only_a_candidate():
    r=check(pair([[1.,1.,1e-8],[0.,2.,1e-8]]),tolerance_mm=1e-6)
    assert r['contact_count']==1 and not r['roundoff_certified']

def test_degenerate_face_excluded_from_links_but_scan_incomplete():
    r=check(pair([[1,1,1],[1,1,-1]]),np.array([[0,1,2],[0,0,3]]))
    assert r['first_degenerate_faces']==[1] and not r['scan_complete']
    assert r['vertex_adjacency']['nonmanifold_vertex_count']==0

@pytest.mark.parametrize('bad',[None,1,np.bool_(True),'yes'])
def test_flag_type_is_strict(bad):
    with pytest.raises(ValueError,match='check_shared_vertices'):
        mesh_contacts(pair([[1,1,1],[1,1,-1]]),FACES,tolerance_mm=0,area_epsilon_mm2=0,
                      check_shared_edges=True,check_shared_vertices=bad)

def test_requires_edge_self_check():
    v=pair([[1,1,1],[1,1,-1]])
    with pytest.raises(ValueError,match='check_shared_vertices'):
        mesh_contacts(v,FACES,tolerance_mm=0,area_epsilon_mm2=0,check_shared_vertices=True)
    with pytest.raises(ValueError):
        mesh_contacts(v,FACES,v,FACES,tolerance_mm=0,area_epsilon_mm2=0,
                      check_shared_edges=True,check_shared_vertices=True)

def test_work_limit_never_reports_complete():
    r=check(pair([[1,1,1],[1,1,-1]]),max_work=1)
    assert r['stop_reason']=='max_work' and not r['scan_complete']

def test_blade_api_propagates_flags_only_to_self_checks():
    x,y=np.meshgrid(np.arange(3.),np.arange(2.))
    grid=np.stack((x+10,y,np.zeros_like(x)),axis=-1)
    main={role:grid+np.array([0,0,i*3.]) for i,role in enumerate(ROLES)}
    r=screen_blade_grids(main,3,tolerance_mm=1e-10,area_epsilon_mm2=0,
                         check_shared_edges=True,check_shared_vertices=True)
    assert r['scan_complete'] and r['check_shared_vertices']
    for c in r['checks']:
        assert c['report']['vertex_adjacency']['enabled'] is (c['second_group'] is None)
    assert not r['whole_geometry_verified']
    with pytest.raises(ValueError,match='check_shared_vertices'):
        screen_blade_grids(main,3,tolerance_mm=0,area_epsilon_mm2=0,check_shared_vertices=True)


def test_branching_link_and_unresolved_examples_are_bounded():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.],[0.,-1.,0.]])
    r=check(v,np.array([[0,1,2],[0,1,3],[0,1,4]]),max_contacts=1)
    assert r['vertex_adjacency']['nonmanifold_vertex_count']==2
    assert r['vertex_adjacency']['nonmanifold_vertex_examples'][0]['branch_vertices']==[1]
    assert not r['scan_complete']


def test_multiple_unresolved_pairs_keep_total_and_limit_examples():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[1.,1e-8,0.],
                [0.,1.,0.],[1e-8,1.,0.],[-1.,0.,0.],[-1.,1e-8,0.]])
    r=check(v,np.array([[0,1,2],[0,3,4],[0,5,6]]),tolerance_mm=1e-6,max_contacts=1)
    a=r['vertex_adjacency']
    assert a['unresolved_count']==3 and a['unresolved_examples_truncated']
    assert len(a['unresolved_examples'])==1 and not r['scan_complete']
