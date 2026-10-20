"""Barycentric displacement bounds, budget failure and identical seam assembly."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
from blade_designer.geometry.mesh_contacts import mesh_contacts
from blade_designer.geometry.role_seams import screen_role_seams,ROLES
from test_conforming_role_grids import surfaces


def build(source,**options):
    return merged_role_error_envelope(source,**{'target_mm':.03,'join_tolerance_mm':1e-8,**options})


def test_exact_join_adds_no_displacement_and_keeps_source_coefficients():
    source=surfaces();before=deepcopy({r:s.across.c for r,s in source.items()});r=build(source)
    assert r['status']=='NUMERIC_TARGET_MET' and r['max_vertex_move_mm']==0
    np.testing.assert_array_equal(r['unmerged_triangle_upper_mm'],r['merged_triangle_upper_mm'])
    for role,s in source.items():np.testing.assert_array_equal(s.across.c,before[role])
    assert r['error_applies_to']=='merged_role_triangles' and not r['contact_ready']


def test_allowed_seam_join_can_exceed_the_original_error_budget():
    source=surfaces();source['ss'].across.c[:,:,0]+=.01
    r=build(source,target_mm=.001,join_tolerance_mm=.02)
    assert r['alignment']['numeric_target_met'] and r['alignment']['role_seam_input_ready']
    assert r['status']=='UNRESOLVED' and r['unresolved_triangles']>0
    assert r['max_vertex_move_mm']==pytest.approx(.01)
    assert r['max_merged_upper_mm']==pytest.approx(.01,abs=1e-13)


def test_local_allowance_is_not_applied_to_unmoved_roles_or_faces():
    source=surfaces();source['ss'].across.c[:,:,0]+=.01
    r=build(source,join_tolerance_mm=.02)
    for role in ROLES:
        mask=np.array(r['mesh']['face_roles'])==role
        if role=='ss':assert np.max(r['triangle_move_allowance_mm'][mask])==pytest.approx(.01)
        else:np.testing.assert_array_equal(r['triangle_move_allowance_mm'][mask],0)


def test_every_barycentric_triangle_displacement_is_enclosed():
    source=surfaces();source['ss'].across.c[:,:,0]+=.01;r=build(source,join_tolerance_mm=.02)
    mesh=r['mesh'];raw=mesh['vertices'][mesh['source_faces']];merged=mesh['vertices'][mesh['faces']]
    for a in np.linspace(0,1,9):
        for b in np.linspace(0,1-a,9):
            w=np.array([a,b,1-a-b])
            delta=np.linalg.norm(np.einsum('j,ijc->ic',w,merged-raw),axis=1)
            assert np.all(delta<=r['triangle_move_allowance_mm']+1e-14)


def test_mesh_used_for_error_is_identical_to_existing_contact_diagnostic():
    source=surfaces(mixed=True);source['ss'].across.c[:,:,0]+=1e-9;r=build(source)
    kwargs={'tolerance_mm':1e-9,'area_epsilon_mm2':1e-16,'check_shared_edges':True,'check_shared_vertices':True}
    direct=mesh_contacts(r['mesh']['vertices'],r['mesh']['faces'],**kwargs)
    existing=screen_role_seams(r['alignment']['grids'],join_tolerance_mm=1e-8,
                               tolerance_mm=1e-9,area_epsilon_mm2=1e-16)
    assert direct==existing['mesh_report']


@pytest.mark.parametrize('options',[{'max_triangles':1},{'join_tolerance_mm':0}])
def test_invalid_assembly_never_returns_a_partial_merged_mesh(options):
    source=surfaces();source['ss'].across.c[:,:,0]+=.1;r=build(source,**options)
    assert r['mesh'] is None and not r['numeric_target_met']
    assert r['status'] in ('RESOURCE_LIMIT','SEAM_MISMATCH')


def test_unresolved_unmerged_error_is_not_reset_by_joining():
    r=build(surfaces(bump=True),max_depth=0,target_mm=1e-6)
    assert r['status']=='UNRESOLVED' and not r['numeric_target_met']
    assert np.all(r['merged_triangle_upper_mm']>=r['unmerged_triangle_upper_mm'])


@pytest.mark.parametrize('options',[{'target_mm':True},{'join_tolerance_mm':-1},{'max_triangles':False},
                                   {'max_seed_cells':0},{'max_depth':13}])
def test_input_validation_is_preserved(options):
    with pytest.raises(ValueError):build(surfaces(),**options)


@pytest.mark.parametrize('scale',[.1,1.,10.])
def test_rigid_transform_and_scale_preserve_merge_displacement(scale):
    source=surfaces();source['ss'].across.c[:,:,0]+=.01
    angle=.7;rot=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
    for surface in source.values():surface.across.c=surface.across.c@rot.T*scale+[12,-3,8]
    r=build(source,target_mm=.03*scale,join_tolerance_mm=.02*scale)
    assert r['max_vertex_move_mm']==pytest.approx(.01*scale,abs=1e-13)
    assert np.all(r['merged_triangle_upper_mm']>=r['unmerged_triangle_upper_mm'])


def test_error_budget_boundary_and_face_count_are_explicit():
    source=surfaces();source['ss'].across.c[:,:,0]+=.01
    r=build(source,join_tolerance_mm=.02)
    assert len(r['merged_triangle_upper_mm'])==r['alignment']['required_triangles']==len(r['mesh']['faces'])
    exact=r['max_merged_upper_mm']
    assert build(source,target_mm=exact+1e-12,join_tolerance_mm=.02)['numeric_target_met']
    assert not build(source,target_mm=exact-1e-12,join_tolerance_mm=.02)['numeric_target_met']
