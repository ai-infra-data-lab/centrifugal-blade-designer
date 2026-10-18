"""Analytic triangle contacts, coplanar negatives and bounded incomplete scans."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.mesh_contacts import mesh_contacts, grid_mesh


A=np.array([[0.,0.,0.],[2.,0.,0.],[0.,2.,0.]])
F=np.array([[0,1,2]])


@pytest.mark.parametrize('b,contact',[
    ([[.5,.5,-1],[.5,.5,1],[1.5,.5,0]],True),
    ([[.1,.1,0],[.5,.1,0],[.1,.5,0]],True),
    ([[2,0,0],[3,0,0],[2,-1,0]],True),
    ([[1,0,0],[2,0,0],[2,-1,0]],True),
    ([[1.5,1.5,0],[3,1.5,0],[1.5,3,0]],False),
    ([[1.5,1.5,-1],[1.5,1.5,1],[3,3,0]],False),
    ([[0,0,.01],[2,0,.01],[0,2,.01]],False),
])
def test_cross_touch_containment_and_separated_analytic_triangles(b,contact):
    b=np.array(b,float)
    for x,y in ((A,b),(b,A)):
        result=mesh_contacts(x,F,y,F,tolerance_mm=0,area_epsilon_mm2=0)
        assert bool(result['contact_count']) is contact
        assert result['scan_complete'] and result['roundoff_certified'] is False


@pytest.mark.parametrize('scale',[.01,1.,100.])
def test_rigid_rotation_translation_and_scale_keep_interior_crossing(scale):
    q,_=np.linalg.qr(np.array([[1.,2.,3.],[-2.,3.,1.],[3.,1.,-2.]]))
    b=np.array([[.5,.5,-1],[.5,.5,1],[1.5,.5,0]])
    a=scale*A@q+np.array([20.,-30.,50.]);b=scale*b@q+np.array([20.,-30.,50.])
    r=mesh_contacts(a,F,b,F,tolerance_mm=1e-10*scale,area_epsilon_mm2=0)
    assert r['contact_pairs']==[[0,0]] and r['scan_complete']


def test_projection_allowance_is_explicit_and_inputs_are_read_only():
    b=A+[0,0,.01];before=deepcopy((A,F,b))
    r=mesh_contacts(A,F,b,F,tolerance_mm=.011,area_epsilon_mm2=0)
    assert r['contact_pairs']==[[0,0]]
    for x,y in zip(before,(A,F,b)):np.testing.assert_array_equal(x,y)


def test_bvh_keeps_original_ids_and_finds_only_known_separated_tiles():
    a=np.concatenate([A+[10*i,0,0] for i in range(20)])
    faces=np.arange(60).reshape(-1,3)
    b=np.array([[.5,.5,-1],[.5,.5,1],[1.5,.5,0]])+[130,0,0]
    r=mesh_contacts(a,faces,b,F,tolerance_mm=0,area_epsilon_mm2=0)
    assert r['contact_pairs']==[[13,0]]
    assert r['node_pair_tests']>1 and r['scan_complete']


def test_duplicate_faces_are_not_hidden_as_adjacency():
    r=mesh_contacts(A,np.array([[0,1,2],[0,2,1]]),tolerance_mm=0,area_epsilon_mm2=0)
    assert r['contact_pairs']==[[0,1]] and r['adjacent_pairs_excluded']==0


def test_shared_edge_is_excluded_and_local_fold_remains_an_unchecked_scope():
    # Both triangles lie on the SAME side of their shared edge and overlap.
    # This deliberately documents the local-adjacency limitation, not a PASS.
    v=np.vstack((A,[.5,.5,0]))
    r=mesh_contacts(v,np.array([[0,1,2],[0,1,3]]),tolerance_mm=0,area_epsilon_mm2=0)
    assert r['adjacent_pairs_excluded']==1 and r['contact_count']==0
    assert r['continuous_surface_certified'] is False and r['containment_checked'] is False


def test_nonlocal_ruled_surface_crossing_with_nonvanishing_analytic_jacobian():
    s=np.array([0,.1,.25,.5,.75,.9,1.]);t=np.linspace(0,1,5)
    grid=np.array([np.column_stack((np.full(len(t),(u-.25)*(u-.75)),
                    np.full(len(t),(u-.25)*(u-.75)*(u-.5)),t)) for u in s])
    v,f=grid_mesh(grid)
    r=mesh_contacts(v,f,tolerance_mm=1e-12,area_epsilon_mm2=0,max_contacts=1000)
    assert r['contact_count']>0 and r['scan_complete']
    assert all(not set(f[i]) & set(f[j]) for i,j in r['contact_pairs'])
    assert len(r['contact_pairs'])==len(set(map(tuple,r['contact_pairs'])))


def test_degenerate_faces_are_listed_and_never_give_complete_clean_result():
    vertices=np.vstack((A,[[0,0,0],[0,0,0],[0,0,0]]))
    r=mesh_contacts(vertices,np.array([[0,1,2],[3,4,5]]),tolerance_mm=0,area_epsilon_mm2=0)
    assert r['first_degenerate_faces']==[1] and r['second_degenerate_faces']==[1]
    assert r['status']=='INCOMPLETE' and not r['scan_complete']


@pytest.mark.parametrize('limits,reason', [({'max_work':1},'max_work'),({'max_contacts':1},'max_contacts')])
def test_limits_propagate_incomplete_evidence(limits,reason):
    r=mesh_contacts(A,F,A,F,tolerance_mm=0,area_epsilon_mm2=0,**limits)
    assert not r['scan_complete'] and r['stop_reason']==reason
    assert r['status']!='NO_CONTACT_OBSERVED'


@pytest.mark.parametrize('options',[{'tolerance_mm':-1},{'tolerance_mm':np.nan},{'tolerance_mm':True},
    {'area_epsilon_mm2':np.inf},{'area_epsilon_mm2':-1},{'max_work':0},{'max_work':True},
    {'max_contacts':0},{'max_triangles':0},{'max_triangles':1.5}])
def test_invalid_options_rejected(options):
    arguments={'tolerance_mm':0,'area_epsilon_mm2':0,**options}
    with pytest.raises(ValueError):mesh_contacts(A,F,**arguments)


@pytest.mark.parametrize('v,f',[(A,[[0.,1.,2.]]),(A,[[0,1,3]]),(A,[[-1,1,2]]),
    (A,[]),(A+np.nan,F),(A.astype(complex),F)])
def test_invalid_geometry_is_not_silently_repaired(v,f):
    with pytest.raises(ValueError):mesh_contacts(v,f,tolerance_mm=0,area_epsilon_mm2=0)


def test_partial_second_mesh_and_oversized_grid_are_rejected():
    with pytest.raises(ValueError):mesh_contacts(A,F,A,tolerance_mm=0,area_epsilon_mm2=0)
    with pytest.raises(ValueError):mesh_contacts(A,np.array([[0,1,2],[0,1,2]]),
        tolerance_mm=0,area_epsilon_mm2=0,max_triangles=1)
    with pytest.raises(ValueError):grid_mesh(np.zeros((1,4,3)))


def test_nonfinite_intermediate_arithmetic_is_rejected_instead_of_reporting_no_contact():
    with pytest.raises(ValueError,match='Non-finite'):
        mesh_contacts(A*1e200,F,A*1e200,F,tolerance_mm=0,area_epsilon_mm2=0)


def test_coarse_grid_can_miss_a_true_curved_contact_and_is_never_a_certificate():
    s=np.array([0.,.5,1.]);t=np.linspace(0,1,3)
    first=np.array([np.column_stack((t,np.full(len(t),u),0*t)) for u in s])
    second=first.copy();second[:,:,2]=(s[:,None]-.37)**2-.001
    assert second[:,:,2].min()>0 and (0.37-.37)**2-.001<0
    v,f=grid_mesh(first);w,g=grid_mesh(second)
    result=mesh_contacts(v,f,w,g,tolerance_mm=0,area_epsilon_mm2=0)
    assert result['status']=='NO_CONTACT_OBSERVED' and result['scan_complete']
    assert result['continuous_surface_certified'] is False


def test_fully_nested_solids_have_no_surface_contact_but_containment_is_unchecked():
    outer=np.array([[0.,0.,0.],[10.,0.,0.],[0.,10.,0.],[0.,0.,10.]])
    inner=np.array([[1.,1.,1.],[2.,1.,1.],[1.,2.,1.],[1.,1.,2.]])
    faces=np.array([[0,1,2],[0,1,3],[0,2,3],[1,2,3]])
    result=mesh_contacts(outer,faces,inner,faces,tolerance_mm=0,area_epsilon_mm2=0)
    assert result['status']=='NO_CONTACT_OBSERVED' and result['scan_complete']
    assert result['containment_checked'] is False
