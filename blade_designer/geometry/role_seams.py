"""Explicit contour-role seam topology for diagnostic triangle meshes only."""
from collections.abc import Mapping
import numpy as np
from .mesh_contacts import grid_mesh,mesh_contacts,_positive_int,_nonnegative


ROLES=('le','ps','te','ss')
SEAMS=(('le',0,'ss',0),('le',-1,'ps',0),('te',0,'ps',-1),('te',-1,'ss',-1))


def screen_role_seams(grids, *, join_tolerance_mm, tolerance_mm, area_epsilon_mm2,
                      max_work=500000,max_contacts=100,max_triangles=20000):
    """Screen all four roles with explicitly paired Span boundary samples.

    Rows MUST represent identical physical Span locations. Only declared seam
    endpoints may share IDs. No spatial search/welding of interior samples.
    Matched endpoints use the earlier role's coordinates, with displacement
    reported. This bounded diagnostic merge never changes input geometry.
    """
    for value,name in ((join_tolerance_mm,'join_tolerance_mm'),(tolerance_mm,'tolerance_mm'),
                       (area_epsilon_mm2,'area_epsilon_mm2')):_nonnegative(value,name)
    for value,name in ((max_work,'max_work'),(max_contacts,'max_contacts'),
                       (max_triangles,'max_triangles')):_positive_int(value,name)
    if not isinstance(grids,Mapping) or set(grids)!=set(ROLES):
        raise ValueError('All four LE/PS/TE/SS grids must be supplied.')
    vertices=[];faces=[];indices={};face_roles=[];nv=0;nf=0;span_count=None
    for role in ROLES:
        grid=np.asarray(grids[role])
        if grid.ndim!=3 or min(grid.shape[:2])<2:
            raise ValueError('Role grids require at least two Span and contour samples.')
        nf+=2*(grid.shape[0]-1)*(grid.shape[1]-1)
        if nf>max_triangles:raise ValueError('Combined role mesh exceeds max_triangles.')
        v,f=grid_mesh(grid)
        if span_count is not None and span_count!=grid.shape[0]:
            raise ValueError('Role grids must have corresponding Span rows.')
        span_count=grid.shape[0]
        indices[role]=np.arange(nv,nv+len(v)).reshape(grid.shape[:2])
        vertices.append(v);faces.append(f+nv);face_roles.extend([role]*len(f));nv+=len(v)
    vertices=np.concatenate(vertices);faces=np.concatenate(faces)
    roots=np.arange(nv);seams=[]
    with np.errstate(over='raise',invalid='raise'):
        for a,ia,b,ib in SEAMS:
            first=indices[a][:,ia];second=indices[b][:,ib]
            try:distances=np.linalg.norm(vertices[first]-vertices[second],axis=1)
            except FloatingPointError as exc:raise ValueError('Non-finite role seam distance arithmetic.') from exc
            if not np.isfinite(distances).all():raise ValueError('Non-finite role seam distances.')
            matched=distances<=join_tolerance_mm
            # Every boundary vertex belongs to exactly one declared pair.
            roots[np.maximum(first[matched],second[matched])]=np.minimum(first[matched],second[matched])
            bad=np.flatnonzero(~matched)
            seams.append({'first_role':a,'first_end':ia,'second_role':b,'second_end':ib,
                          'matched_vertices':int(matched.sum()),'unmatched_vertices':len(bad),
                          'max_gap_mm':float(distances.max()),
                          'max_merge_displacement_mm':float(distances[matched].max()) if matched.any() else 0.,
                          'unmatched_row_examples':bad[:max_contacts].tolist()})
    report=mesh_contacts(vertices,roots[faces],tolerance_mm=tolerance_mm,
        area_epsilon_mm2=area_epsilon_mm2,max_work=max_work,max_contacts=max_contacts,
        max_triangles=max_triangles,check_shared_edges=True,check_shared_vertices=True)
    complete=report['scan_complete'] and all(s['unmatched_vertices']==0 for s in seams)
    return {'status':'CONTACT_CANDIDATES_FOUND' if report['contact_count'] else
                    'NO_CONTACT_OBSERVED' if complete else 'INCOMPLETE',
            'scan_complete':bool(complete),'seams':seams,'mesh_report':report,
            'contact_role_pairs':[[face_roles[a],face_roles[b]] for a,b in report['contact_pairs']],
            'join_tolerance_mm':float(join_tolerance_mm),
            'source_model':'caller_supplied_XYZ_role_grids','units':'mm','axis':'Z',
            'diagnostic_model':'seam_merged_triangle_approximation','source_coordinates_modified':False,
            'unchecked':['Span row physical correspondence','mesh winding and outward orientation',
                         'periodic copies and other blade sets','solid containment',
                         'Hub/Tip caps, walls, disk and fillets','continuous surface between sample points'],
            'continuous_surface_certified':False,'roundoff_certified':False,'whole_geometry_verified':False}
