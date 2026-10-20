"""Source identity, exact triangular parameter coverage and local rechecks."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.contact_sources import source_triangle_patch,surface_fingerprint
from blade_designer.geometry.contact_refinement import refine_source_triangle,refine_contact_pair
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
from blade_designer.geometry.error_aware_contacts import error_aware_mesh_contacts
from test_surface_envelope import patch,plane
from test_surface_triangulation import saddle
from test_conforming_role_grids import surfaces


def domain(half=0):return {'role':'ps','source_face':2,'span_range':[0.,1.],'xi_range':[0.,1.],'diagonal_half':half}


def envelope(source):return merged_role_error_envelope(source,target_mm=.1,join_tolerance_mm=1e-8)


def compare(a,b):
    return error_aware_mesh_contacts(a['vertices'],a['faces'],a['triangle_upper_mm'],
                                    b['vertices'],b['faces'],b['triangle_upper_mm'],
                                    clearance_mm=0,area_epsilon_mm2=0)


def test_every_recorded_face_maps_to_original_role_cell_and_diagonal():
    source=surfaces(mixed=True);r=envelope(source)
    for index,face in enumerate(r['mesh']['source_faces']):
        p=source_triangle_patch(r,index);s0,s1=p['span_range'];t0,t1=p['xi_range']
        grid=source[p['role']].evaluate_grid([s0,s1],[t0,t1])
        corners=grid[[0,1,1,0],[0,0,1,1]];ids=[0,1,2] if p['diagonal_half']==0 else [0,2,3]
        np.testing.assert_allclose(r['mesh']['vertices'][face],corners[ids],atol=1e-13,rtol=0)


@pytest.mark.parametrize('field',['vertices','faces','source_faces','face_roles'])
def test_modified_mapping_snapshot_is_rejected(field):
    r=envelope(surfaces())
    if field=='face_roles':r['mesh'][field][0]='ss'
    elif field=='vertices':r['mesh'][field][0,0]+=.01
    else:r['mesh'][field][0,0]=r['mesh'][field][0,1]
    with pytest.raises(ValueError,match='snapshot'):source_triangle_patch(r,0)


@pytest.mark.parametrize('face',[True,-1,100000,None,1.5])
def test_invalid_face_id_rejected(face):
    with pytest.raises(ValueError):source_triangle_patch(envelope(surfaces()),face)


@pytest.mark.parametrize('half',[0,1])
@pytest.mark.parametrize('depth',[0,1,2,3])
def test_dyadic_leaves_cover_only_the_original_parameter_triangle(half,depth):
    r=refine_source_triangle(patch(saddle,2,(0.,1.)),domain(half),target_mm=0,max_depth=depth,max_cells=1000)
    points=r['parameter_vertices'][r['faces']]
    assert np.all(points[:,:,0]>=points[:,:,1]) if half==0 else np.all(points[:,:,0]<=points[:,:,1])
    edges=points[:,1:]-points[:,:1]
    area=np.abs(edges[:,0,0]*edges[:,1,1]-edges[:,0,1]*edges[:,1,0])/2
    assert area.sum()==pytest.approx(.5)
    assert r['max_upper_mm']==pytest.approx(.25/4**depth,abs=1e-13)
    assert len(r['faces'])==4**depth


def test_curved_surface_separation_is_resolved_without_changing_sources():
    a=patch(saddle,2,(0.,1.));b=patch(lambda s,t:plane(s,t)+[0,0,1.2],2,(0.,1.))
    before=deepcopy(a.across.c)
    coarse=refine_source_triangle(a,domain(),target_mm=1,max_depth=0)
    second=refine_source_triangle(b,domain(),target_mm=.01)
    assert compare(coarse,second)['status']=='UNCERTAIN'
    fine=refine_source_triangle(a,domain(),target_mm=.01)
    assert compare(fine,second)['numeric_separated']
    np.testing.assert_array_equal(a.across.c,before)


def test_actual_crossing_does_not_become_separated_after_refinement():
    a=refine_source_triangle(patch(saddle,2,(0.,1.)),domain(),target_mm=.01)
    b=refine_source_triangle(patch(lambda s,t:plane(s,t)+[0,0,.5],2,(0.,1.)),domain(),target_mm=.01)
    assert not compare(a,b)['numeric_separated']


@pytest.mark.parametrize('options',[{'max_depth':0},{'max_cells':1}])
def test_resource_limit_retains_complete_parent_domain_and_valid_bounds(options):
    r=refine_source_triangle(patch(saddle,2,(0.,1.)),domain(),target_mm=1e-9,**options)
    assert r['status']=='UNRESOLVED' and not r['numeric_target_met']
    assert len(r['faces'])==1 and r['max_upper_mm']==pytest.approx(.25)


def test_recorded_pair_uses_original_sources_and_does_not_mutate_envelope():
    source=surfaces();r=envelope(source);before=deepcopy(r['mesh']['vertices'])
    result=refine_contact_pair(source,r,0,4,target_mm=.01,clearance_mm=0,area_epsilon_mm2=0)
    assert result['source_identity_checked'] and result['contact_report']['numeric_separated']
    assert result['source_basis']=='original_unmerged_splines' and not result['whole_geometry_verified']
    np.testing.assert_array_equal(r['mesh']['vertices'],before)


def test_changed_interior_with_unchanged_corners_is_rejected():
    source=surfaces();r=envelope(source);role=r['mesh']['face_roles'][0]
    corners=source[role].evaluate_grid([0,1],[0,1])
    before=surface_fingerprint(source[role]);source[role].across.c[1,1,0]+=.01
    np.testing.assert_array_equal(source[role].evaluate_grid([0,1],[0,1]),corners)
    assert surface_fingerprint(source[role])!=before
    with pytest.raises(ValueError,match='Source surface changed'):
        refine_contact_pair(source,r,0,4,target_mm=.01,clearance_mm=0,area_epsilon_mm2=0)


@pytest.mark.parametrize('options',[{'target_mm':True},{'target_mm':-1},{'max_depth':9},{'max_depth':False},
                                   {'max_cells':0},{'max_cells':True}])
def test_invalid_refinement_options_rejected(options):
    with pytest.raises(ValueError):
        refine_source_triangle(patch(plane),domain(),**{'target_mm':.01,**options})


@pytest.mark.parametrize('bad',[{'span_range':[1,0]},{'xi_range':[0,np.nan]},{'diagonal_half':True},{'diagonal_half':2}])
def test_invalid_parameter_domain_rejected(bad):
    with pytest.raises(ValueError):refine_source_triangle(patch(plane),{**domain(),**bad},target_mm=.01)


def test_nontrivial_source_knot_interval_restriction_matches_dense_surface():
    from scipy.interpolate import make_interp_spline
    s=patch(plane,3,(0.,.5,1.));s.along=s.along.insert_knot(.5,2)
    s.across=make_interp_spline([0.,.5,1.],s.along.c,k=2,axis=1)
    p={**domain(),'xi_range':[.5,1.]}
    r=refine_source_triangle(s,p,target_mm=1e-12)
    assert r['numeric_target_met']
    for xyz,uv in zip(r['vertices'],r['parameter_vertices']):
        np.testing.assert_allclose(xyz,s.evaluate_grid([uv[0]],[uv[1]])[0,0],atol=1e-14)


def test_legacy_missing_snapshot_and_same_triangle_are_rejected():
    source=surfaces();r=envelope(source)
    with pytest.raises(ValueError,match='distinct'):
        refine_contact_pair(source,r,0,0,target_mm=.01,clearance_mm=0,area_epsilon_mm2=0)
    del r['mapping_fingerprint']
    with pytest.raises(ValueError,match='snapshot'):source_triangle_patch(r,0)


def test_modified_parameter_axis_is_rejected():
    r=envelope(surfaces());r['alignment']['span_coordinates'][0]=.01
    with pytest.raises(ValueError,match='snapshot'):source_triangle_patch(r,0)


def test_cubic_surface_error_encloses_independent_barycentric_queries():
    s=patch(lambda u,v:plane(u,v)+np.column_stack((0*v,0*v,u**3*v**2)),4,(0.,.3,.7,1.))
    r=refine_source_triangle(s,domain(1),target_mm=.005,max_depth=2)
    for face,upper in zip(r['faces'],r['triangle_upper_mm']):
        for weights in ([1/3]*3,[.6,.1,.3],[0,.5,.5]):
            uv=np.array(weights)@r['parameter_vertices'][face]
            approx=np.array(weights)@r['vertices'][face]
            actual=s.evaluate_grid([uv[0]],[uv[1]])[0,0]
            assert np.linalg.norm(actual-approx)<=upper+1e-13


@pytest.mark.parametrize('options',[{'clearance_mm':-1},{'max_work':0},{'max_records':False}])
def test_pair_resource_and_clearance_validation(options):
    source=surfaces();r=envelope(source)
    with pytest.raises(ValueError):
        refine_contact_pair(source,r,0,4,**{'target_mm':.01,'clearance_mm':0,'area_epsilon_mm2':0,**options})


def test_local_examples_do_not_consume_nonlocal_face_id_budget():
    from blade_designer.geometry.error_aware_self_contacts import error_aware_self_contacts
    from test_error_aware_self_contacts import grid
    v,f=grid();count=len(v)
    v=np.concatenate((v,v+[0,0,.001]));f=np.concatenate((f,f+count))
    r=error_aware_self_contacts(v,f,np.full(len(f),.01),clearance_mm=0,adjacency_tolerance_mm=1e-10,
                                area_epsilon_mm2=0,max_examples=1)
    assert r['examples'][0]['kind']=='LOCAL_SOURCE_UNCERTAIN'
    assert len(r['nonlocal_examples'])==1 and r['nonlocal_examples_truncated']
    assert r['nonlocal_examples'][0]['kind']=='NONLOCAL_UNCERTAIN'
