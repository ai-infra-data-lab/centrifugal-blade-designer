"""Aligned parameter topology, fresh error bounds and resource protection."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.conforming_role_grids import conforming_role_grids
from blade_designer.geometry.surface_evaluation import fit_surface_spline
from blade_designer.geometry.role_seams import screen_role_seams
from test_role_seams import tube


def surfaces(bump=False,mixed=False):
    result={}
    for role,grid in tube(3,3).items():
        a,b=grid[0,0,:2],grid[0,-1,:2]
        spans=(0.,.2,.4,.7,1.) if mixed and role=='le' else (0.,.5,1.)
        n=5 if mixed and role=='te' else 3;t=np.linspace(0,1,n)
        rows=[]
        for s in spans:
            xy=(1-t[:,None])*a+t[:,None]*b
            if bump and role=='ps':xy[:,1]-=8*s*(1-s)*t*(1-t)
            rows.append(np.column_stack((xy,np.full(n,4*s))))
        result[role]=fit_surface_spline(rows,n,spans=spans)
    return result


def build(s,**kwargs):
    return conforming_role_grids(s,**{'target_mm':.03,'join_tolerance_mm':1e-8,**kwargs})


def test_mixed_knot_and_role_densities_have_identical_span_rows_and_clean_topology():
    source=surfaces(mixed=True);before=deepcopy({r:s.across.c for r,s in source.items()})
    r=build(source)
    assert r['status']=='NUMERIC_TARGET_MET' and r['parameter_conforming']
    assert r['role_seam_input_ready'] and not r['contact_ready']
    assert len({len(g) for g in r['grids'].values()})==1
    assert len({g.shape[1] for g in r['grids'].values()})>1
    contact=screen_role_seams(r['grids'],join_tolerance_mm=1e-8,tolerance_mm=1e-9,area_epsilon_mm2=1e-16)
    assert contact['status']=='NO_CONTACT_OBSERVED' and contact['scan_complete']
    for role,s in source.items():np.testing.assert_array_equal(s.across.c,before[role])


def test_local_bump_closes_all_span_cuts_and_rechecks_analytic_triangle_error():
    r=build(surfaces(bump=True))
    assert r['numeric_target_met'] and r['required_triangles']>8
    u=r['span_coordinates'];v=r['role_coordinates']['ps'];g=r['grids']['ps']
    for i,(s0,s1) in enumerate(zip(u,u[1:])):
        for j,(t0,t1) in enumerate(zip(v,v[1:])):
            x=np.linspace(0,1,11)[:,None,None];y=np.linspace(0,1,13)[None,:,None]
            a,b,c,d=g[[i,i+1,i+1,i],[j,j,j+1,j+1]]
            tri=np.where(x>=y,a+x*(b-a)+y*(c-b),a+y*(d-a)+x*(c-d))
            s=s0+(s1-s0)*x[...,0];t=t0+(t1-t0)*y[...,0]
            exact=np.stack(np.broadcast_arrays(10+2*t,-8*s*(1-s)*t*(1-t),4*s),axis=-1)
            assert np.linalg.norm(exact-tri,axis=-1).max()<=r['role_reports']['ps']['cell_upper_mm'][i,j]+1e-12


def test_tensor_explosion_does_not_return_partial_grids_or_claim_readiness():
    r=build(surfaces(bump=True),max_triangles=9)
    assert r['status']=='RESOURCE_LIMIT' and r['required_triangles']>9
    assert r['grids']=={} and not r['role_seam_input_ready'] and not r['parameter_conforming']


def test_seed_limit_and_depth_unmet_remain_visible():
    r=build(surfaces(bump=True),max_depth=0,target_mm=1e-6)
    assert r['status']=='UNRESOLVED' and not r['numeric_target_met']
    assert r['seed_unresolved_cells']['ps']>0
    assert r['role_reports']['ps']['unresolved_cells']>0


def test_seam_mismatch_is_not_repaired_or_hidden():
    source=surfaces();source['ss'].across.c[:,:,0]+=.1
    before=source['ss'].across.c.copy();r=build(source)
    assert r['status']=='SEAM_MISMATCH' and not r['role_seam_input_ready']
    assert any(s['unmatched_rows']>0 for s in r['seams'])
    np.testing.assert_array_equal(source['ss'].across.c,before)


@pytest.mark.parametrize('options',[{'target_mm':True},{'target_mm':float('nan')},
    {'join_tolerance_mm':-1},{'join_tolerance_mm':True},{'max_triangles':0},
    {'max_triangles':True},{'max_depth':-1},{'max_seed_cells':False}])
def test_invalid_options(options):
    with pytest.raises(ValueError):build(surfaces(),**options)


def test_missing_roles_and_unsupported_surfaces_are_rejected():
    s=surfaces();del s['te']
    with pytest.raises(ValueError):build(s)
    s=surfaces();s['te']=None
    with pytest.raises(ValueError):build(s)


def test_combined_triangle_cap_is_exact_and_bounds_match_the_returned_grid():
    source=surfaces(mixed=True);r=build(source);count=r['required_triangles']
    assert count==sum(2*(g.shape[0]-1)*(g.shape[1]-1) for g in r['grids'].values())
    assert build(source,max_triangles=count)['parameter_conforming']
    assert build(source,max_triangles=count-1)['status']=='RESOURCE_LIMIT'
    for role,grid in r['grids'].items():
        assert r['role_reports'][role]['cell_upper_mm'].shape==tuple(np.array(grid.shape[:2])-1)


def test_nonzero_seam_allowance_does_not_weld_returned_coordinates_or_relabel_error():
    source=surfaces();source['ss'].across.c[:,:,0]+=1e-9;r=build(source)
    assert r['role_seam_input_ready']
    assert 0<np.linalg.norm(r['grids']['le'][:,0]-r['grids']['ss'][:,0],axis=1).max()<1e-8
    assert r['error_applies_to']=='unmerged_role_triangles' and not r['contact_ready']
    contact=screen_role_seams(r['grids'],join_tolerance_mm=1e-8,tolerance_mm=1e-9,area_epsilon_mm2=1e-16)
    assert max(s['max_merge_displacement_mm'] for s in contact['seams'])>0
