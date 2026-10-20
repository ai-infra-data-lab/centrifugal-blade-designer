"""Independent analytic open tubes and cross-role negatives; no source welding."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.role_seams import screen_role_seams,SEAMS


def tube(rows=3,columns=3):
    contour={'le':((10,2),(10,0)),'ps':((10,0),(12,0)),
             'te':((12,0),(12,2)),'ss':((10,2),(12,2))}
    result={}
    for role,(a,b) in contour.items():
        g=np.empty((rows,columns,3));g[:,:,:2]=np.linspace(a,b,columns)
        g[:,:,2]=np.linspace(0,4,rows)[:,None];result[role]=g
    return result


def screen(grids,**kwargs):
    return screen_role_seams(grids,**{'join_tolerance_mm':0.,'tolerance_mm':1e-10,
                                     'area_epsilon_mm2':1e-16,**kwargs})


@pytest.mark.parametrize('rows,columns',[(2,2),(3,3),(4,5)])
def test_normal_contour_role_seams_and_links(rows,columns):
    grids=tube(rows,columns);before=deepcopy(grids);r=screen(grids)
    assert r['status']=='NO_CONTACT_OBSERVED' and r['scan_complete']
    assert all(s['matched_vertices']==rows and s['unmatched_vertices']==0 for s in r['seams'])
    assert r['mesh_report']['adjacency']['nonmanifold_edge_count']==0
    assert r['mesh_report']['vertex_adjacency']['nonmanifold_vertex_count']==0
    assert not r['whole_geometry_verified'] and not r['continuous_surface_certified']
    for role in grids:np.testing.assert_array_equal(grids[role],before[role])


@pytest.mark.parametrize('seam',SEAMS)
def test_each_declared_seam_gap_is_incomplete(seam):
    a,ia,b,ib=seam;g=tube();g[b][:,ib,0]+=.001
    r=screen(g)
    assert not r['scan_complete'] and r['status']!='NO_CONTACT_OBSERVED'
    entry=next(s for s in r['seams'] if (s['first_role'],s['first_end'],s['second_role'],s['second_end'])==seam)
    assert entry['unmatched_vertices']==3 and entry['max_gap_mm']==pytest.approx(.001)


def test_explicit_merge_displacement_is_reported_without_changing_sources():
    g=tube();g['ss'][:,0,0]+=1e-8;before=deepcopy(g)
    r=screen(g,join_tolerance_mm=2e-8)
    assert r['scan_complete']
    assert r['seams'][0]['max_merge_displacement_mm']==pytest.approx(1e-8)
    for role in g:np.testing.assert_array_equal(g[role],before[role])


def test_cross_role_fold_at_a_shared_edge_is_not_an_expected_seam():
    g=tube();g['ps'][:,1,:2]=[10,1]
    r=screen(g)
    assert r['status']=='CONTACT_CANDIDATES_FOUND'
    assert any(set(pair)=={'le','ps'} for pair in r['contact_role_pairs'])
    assert 'shared_edge_overlap_candidate' in r['mesh_report']['contact_kinds']


def test_interior_same_coordinates_are_not_welded_or_omitted():
    g=tube();g['te'][:,1,:2]=[10,1]
    r=screen(g)
    assert all(s['unmatched_vertices']==0 for s in r['seams'])
    assert r['status']=='CONTACT_CANDIDATES_FOUND'
    assert any(set(pair)=={'le','te'} for pair in r['contact_role_pairs'])


@pytest.mark.parametrize('scale',[.1,1.,100.])
def test_rigid_transform_and_scale_preserve_clean_seams(scale):
    g=tube();angle=.7
    rotation=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
    g={r:v@rotation.T*scale+np.array([30,-4,6]) for r,v in g.items()}
    assert screen(g)['status']=='NO_CONTACT_OBSERVED'


@pytest.mark.parametrize('options',[{'join_tolerance_mm':True},{'join_tolerance_mm':float('nan')},
    {'join_tolerance_mm':-1},{'max_triangles':True},{'max_work':0}])
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValueError):screen(tube(),**options)


def test_limits_and_degenerate_faces_do_not_become_pass():
    assert screen(tube(),max_work=1)['scan_complete'] is False
    g=tube();g['ps'][:,1]=g['ps'][:,0]
    assert screen(g)['scan_complete'] is False
    with pytest.raises(ValueError,match='max_triangles'):screen(tube(),max_triangles=2)


def test_missing_role_and_unmatched_span_counts_are_rejected():
    g=tube();del g['te']
    with pytest.raises(ValueError,match='four'):screen(g)
    g=tube();g['te']=tube(4)['te']
    with pytest.raises(ValueError,match='Span rows'):screen(g)


def test_nonfinite_input_and_arithmetic_are_rejected():
    g=tube();g['le'][1,1,0]=np.nan
    with pytest.raises(ValueError):screen(g)
    g=tube();g['ss'][:,0,0]=1e200
    with pytest.raises(ValueError,match='arithmetic'):screen(g)


def test_contact_limit_reports_incomplete_and_does_not_hide_the_contact():
    g=tube();g['te'][:,1,:2]=[10,1]
    r=screen(g,max_contacts=1)
    assert r['status']=='CONTACT_CANDIDATES_FOUND' and not r['scan_complete']
    assert r['mesh_report']['stop_reason']=='max_contacts'
