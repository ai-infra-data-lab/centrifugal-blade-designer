"""Tensor closure of adaptive role cells, without modifying source surfaces.

Shared parameter rows do not prove physical Span correspondence. Bounds apply
to UNMERGED triangles, before any diagnostic seam-coordinate displacement.
"""
from collections.abc import Mapping
import numpy as np
from .role_seams import ROLES,SEAMS
from .surface_triangulation import adaptive_triangle_envelope,_cell
from .surface_envelope import _control_net,_insert
from .mesh_contacts import _positive_int,_nonnegative


def conforming_role_grids(surfaces, *, target_mm,join_tolerance_mm,
                          max_depth=6,max_seed_cells=1024,max_triangles=20000):
    """Return aligned explicit grids and re-evaluated unmerged error bounds.

    Union of all role Span cuts, with a per-role union of contour cuts. No
    fuzzy knot merging or refit. Closure can exceed the local seed budget;
    combined triangle limits are checked before tensor allocation/insertion.
    Existing generation, display and contact/export gates are not changed.
    """
    _nonnegative(target_mm,'target_mm');_nonnegative(join_tolerance_mm,'join_tolerance_mm')
    _positive_int(max_triangles,'max_triangles')
    if not isinstance(surfaces,Mapping) or set(surfaces)!=set(ROLES):
        raise ValueError('All four LE/PS/TE/SS spline surfaces must be supplied.')
    seeds={r:adaptive_triangle_envelope(surfaces[r],target_mm=target_mm,max_depth=max_depth,
                                      max_cells=max_seed_cells) for r in ROLES}
    spans=np.unique([v for r in ROLES for c in seeds[r]['cells'] for v in c['span_range']])
    coordinates={r:np.unique([v for c in seeds[r]['cells'] for v in c['xi_range']]) for r in ROLES}
    counts={r:2*(len(spans)-1)*(len(coordinates[r])-1) for r in ROLES}
    total=sum(counts.values())
    result={'grids':{},'span_coordinates':spans,'role_coordinates':coordinates,
        'required_triangles':total,'role_triangle_counts':counts,'max_triangles':max_triangles,
        'seed_unresolved_cells':{r:seeds[r]['unresolved_cells'] for r in ROLES},
        'target_mm':float(target_mm),'join_tolerance_mm':float(join_tolerance_mm),
        'parameter_conforming':False,'role_seam_input_ready':False,'numeric_target_met':False,
        'contact_ready':False,'continuous_surface_certified':False,'roundoff_certified':False,
        'whole_geometry_verified':False,'error_applies_to':'unmerged_role_triangles',
        'unchecked':['physical Span correspondence','seam curves between sampled rows',
                     'triangle validity, contact and containment','seam merge error propagation',
                     'periodic copies and other blade sets','CAD/STEP final surfaces']}
    if total>max_triangles:
        return {**result,'status':'RESOURCE_LIMIT','reason':'tensor_closure_exceeds_max_triangles'}
    reports={};grids={};seams=[]
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            for role in ROLES:
                knots,degrees,net=_control_net(surfaces[role]);p,q=degrees
                for axis,values in enumerate((spans,coordinates[role])):
                    k=degrees[axis]
                    knots[axis],net=_insert(knots[axis],net,k,axis,
                        {v:k if 0<v<1 else k+1 for v in values})
                grid=surfaces[role].evaluate_grid(spans,coordinates[role])
                if not np.isfinite(grid).all():raise ValueError('Conforming grids must be finite.')
                upper=np.empty((len(spans)-1,len(coordinates[role])-1))
                corner_residual=0.
                for i,(u0,u1) in enumerate(zip(spans,spans[1:])):
                    for j,(v0,v1) in enumerate(zip(coordinates[role],coordinates[role][1:])):
                        cell=_cell(net[i*p:i*p+p+1,j*q:j*q+q+1],(u0,u1,v0,v1),0)
                        actual=grid[[i,i+1,i+1,i],[j,j,j+1,j+1]]
                        # Reconcile pole/corner arithmetic with actual evaluated mesh vertices.
                        shift=float(np.max(np.linalg.norm(actual-cell['corners'],axis=1)))
                        corner_residual=max(corner_residual,shift)
                        upper[i,j]=cell['upper']+shift
                if not np.isfinite(upper).all():raise ValueError('Conforming error bounds must be finite.')
                grids[role]=grid
                reports[role]={'cell_upper_mm':upper,'max_upper_mm':float(upper.max()),
                    'unresolved_cells':int(np.sum(upper>target_mm)),
                    'max_corner_reconciliation_mm':corner_residual}
            for a,ia,b,ib in SEAMS:
                gap=np.linalg.norm(grids[a][:,ia]-grids[b][:,ib],axis=1)
                if not np.isfinite(gap).all():raise ValueError('Seam gaps must be finite.')
                seams.append({'first_role':a,'first_end':ia,'second_role':b,'second_end':ib,
                    'max_gap_mm':float(gap.max()),'unmatched_rows':int(np.sum(gap>join_tolerance_mm))})
    except FloatingPointError as exc:
        raise ValueError('Non-finite arithmetic in conforming grids.') from exc
    met=all(r['unresolved_cells']==0 for r in reports.values())
    joined=all(s['unmatched_rows']==0 for s in seams)
    return {**result,'grids':grids,'role_reports':reports,'seams':seams,'parameter_conforming':True,
        'role_seam_input_ready':joined,'numeric_target_met':met,
        'status':'SEAM_MISMATCH' if not joined else 'NUMERIC_TARGET_MET' if met else 'UNRESOLVED',
        'reason':'sampled_seam_mismatch' if not joined else 'target' if met else 'rechecked_bound_above_target'}
