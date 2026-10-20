"""Analytic separation inequalities, uncertainty and merged-bound integration."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.error_aware_contacts import error_aware_mesh_contacts,_separation_lower
from blade_designer.geometry.mesh_contacts import mesh_contacts
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
from test_conforming_role_grids import surfaces


TRI=np.array([[0.,0,0],[2,0,0],[0,2,0]])
FACE=np.array([[0,1,2]])


def screen(gap,errors=(.1,.2),**options):
    return error_aware_mesh_contacts(TRI,FACE,[errors[0]],TRI+[0,0,gap],FACE,[errors[1]],
                                    **{'clearance_mm':0.,'area_epsilon_mm2':1e-16,**options})


@pytest.mark.parametrize('gap,expected',[(.31,'NUMERIC_SEPARATED'),(.3,'UNCERTAIN'),(.1,'UNCERTAIN'),(0,'CONTACT_CANDIDATES_FOUND')])
def test_parallel_planes_against_analytic_sum_of_errors(gap,expected):
    report=screen(gap)
    assert report['status']==expected and report['scan_complete']
    assert report['numeric_separated']==(expected=='NUMERIC_SEPARATED')
    assert not report['roundoff_certified'] and not report['continuous_surface_certified']


def test_no_triangle_contact_can_still_be_uncertain_due_to_surface_error():
    b=TRI+[0,0,.1]
    old=mesh_contacts(TRI,FACE,b,FACE,tolerance_mm=0,area_epsilon_mm2=0)
    assert old['status']=='NO_CONTACT_OBSERVED'
    assert screen(.1)['status']=='UNCERTAIN'


def test_required_clearance_is_added_not_used_as_sat_tolerance():
    assert screen(.5,clearance_mm=.3)['status']=='UNCERTAIN'
    assert screen(.5,clearance_mm=.1)['numeric_separated']
    assert screen(0,clearance_mm=10)['contact_candidates']==1


def test_equality_is_not_strict_separation():
    assert screen(.5,errors=(.25,.25))['status']=='UNCERTAIN'
    assert screen(.5001,errors=(.25,.25))['numeric_separated']


def test_coplanar_disjoint_and_crossing_triangles():
    for shift,status in [([3,0,0],'NUMERIC_SEPARATED'),([.5,0,0],'CONTACT_CANDIDATES_FOUND')]:
        r=error_aware_mesh_contacts(TRI,FACE,[0],TRI+shift,FACE,[0],clearance_mm=0,area_epsilon_mm2=0)
        assert r['status']==status


def test_projection_lower_is_not_euclidean_distance():
    # Parallel triangles displaced diagonally: bound cannot exceed actual distance.
    b=TRI+[3,3,1]
    lower=_separation_lower(TRI,b)
    assert 0<lower<=3  # closest (1,1,0) to (3,3,1): distance 3.
    assert lower<3


@pytest.mark.parametrize('angle',[0,.4,1.7])
def test_rotation_translation_and_mesh_order_preserve_safe_classification(angle):
    rot=np.array([[1,0,0],[0,np.cos(angle),-np.sin(angle)],[0,np.sin(angle),np.cos(angle)]])
    a=TRI@rot.T+[12,-5,7];b=(TRI+[0,0,.2])@rot.T+[12,-5,7]
    for first,second in [(a,b),(b,a)]:
        r=error_aware_mesh_contacts(first,FACE,[.1],second,FACE,[.2],clearance_mm=0,area_epsilon_mm2=0)
        assert r['status']=='UNCERTAIN'


def test_degenerate_face_and_resource_limits_never_clear():
    assert screen(100,max_work=1)['scan_complete']  # root AABBs suffice
    assert screen(0,max_work=1)['status']=='INCOMPLETE'
    r=error_aware_mesh_contacts(TRI,[[0,0,2]],[0],TRI+[0,0,10],FACE,[0],clearance_mm=0,area_epsilon_mm2=0)
    assert r['status']=='INCOMPLETE' and r['first_degenerate_faces']==[0]
    r=screen(.1,max_records=1)
    assert r['status']=='INCOMPLETE' and r['stop_reason']=='max_records'
    assert not r['numeric_separated']


def test_per_face_bounds_keep_original_ids_and_do_not_broadcast():
    a=np.concatenate((TRI,TRI+[0,0,2]));f=np.array([[0,1,2],[3,4,5]])
    r=error_aware_mesh_contacts(a,f,[0,1],TRI+[0,0,3],FACE,[.1],clearance_mm=0,area_epsilon_mm2=0)
    assert r['status']=='UNCERTAIN'
    assert [(v['first_face'],v['second_face']) for v in r['records']]==[(1,0)]


@pytest.mark.parametrize('bad',[[-1],[np.nan],[np.inf],[True],0,[0,0],[1j]])
def test_invalid_error_bounds_rejected(bad):
    with pytest.raises(ValueError):
        error_aware_mesh_contacts(TRI,FACE,bad,TRI,FACE,[0],clearance_mm=0,area_epsilon_mm2=0)


@pytest.mark.parametrize('options',[{'clearance_mm':-1},{'clearance_mm':True},{'area_epsilon_mm2':np.nan},
                                   {'max_work':0},{'max_records':False},{'max_triangles':0}])
def test_invalid_options_rejected(options):
    with pytest.raises(ValueError):screen(1,**options)


def test_overflow_is_an_input_error_not_a_separation_success():
    with pytest.raises(ValueError):screen(1,errors=(1e308,1e308),clearance_mm=1e308)


def test_merged_role_bounds_feed_exact_mesh_without_changing_sources():
    source=surfaces();source['ss'].across.c[:,:,0]+=.01
    before=deepcopy({k:s.across.c for k,s in source.items()})
    result=merged_role_error_envelope(source,target_mm=.03,join_tolerance_mm=.02)
    m=result['mesh'];bounds=result['merged_triangle_upper_mm']
    vertices=m['vertices'].copy();faces=m['faces'].copy();errors=bounds.copy()
    r=error_aware_mesh_contacts(vertices,faces,bounds,vertices+[0,0,5],faces,bounds,
                                clearance_mm=.1,area_epsilon_mm2=1e-16)
    assert r['numeric_separated'] and not r['whole_geometry_verified']
    np.testing.assert_array_equal(vertices,m['vertices']);np.testing.assert_array_equal(faces,m['faces'])
    np.testing.assert_array_equal(bounds,errors)
    for role,s in source.items():np.testing.assert_array_equal(s.across.c,before[role])


def test_bvh_report_agrees_with_all_triangle_pair_inequalities():
    # >8 triangles forces BVH branches, with varying error budgets.
    a=np.concatenate([TRI+[i*4,0,0] for i in range(12)])
    f=np.arange(36).reshape(-1,3);errors=np.linspace(.01,.12,12)
    b=a+[0,0,.2]
    r=error_aware_mesh_contacts(a,f,errors,b,f,errors,clearance_mm=.01,area_epsilon_mm2=0,max_records=1000)
    expected={(i,j) for i in range(12) for j in range(12)
              if _separation_lower(a[f[i]],b[f[j]])<=errors[i]+errors[j]+.01}
    assert r['scan_complete'] and r['status']=='UNCERTAIN'
    assert {(v['first_face'],v['second_face']) for v in r['records']}==expected


def test_source_planes_can_touch_while_approximation_triangles_do_not():
    # The two exact planes both lie at Z=.1; their approximations at 0 and .2.
    r=screen(.2,errors=(.1,.1))
    assert r['status']=='UNCERTAIN' and not r['numeric_separated']
    assert r['contact_candidates']==0


@pytest.mark.parametrize('scale',[.01,1.,100.])
def test_units_scale_errors_and_clearance_together(scale):
    r=error_aware_mesh_contacts(TRI*scale,FACE,[.1*scale],(TRI+[0,0,.4])*scale,FACE,[.2*scale],
                                clearance_mm=.2*scale,area_epsilon_mm2=0)
    assert r['status']=='UNCERTAIN'


def test_non_coplanar_crossing_is_a_candidate_even_with_zero_error():
    b=np.array([[.5,.5,-1],[.5,.5,1],[1.5,.5,0]])
    r=error_aware_mesh_contacts(TRI,FACE,[0],b,FACE,[0],clearance_mm=0,area_epsilon_mm2=0)
    assert r['status']=='CONTACT_CANDIDATES_FOUND' and r['scan_complete']
    assert r['records'][0]['projection_lower_mm']==0
