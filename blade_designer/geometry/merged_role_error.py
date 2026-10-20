"""Propagate diagnostic seam displacements onto corresponding triangle bounds."""
import numpy as np
from .conforming_role_grids import conforming_role_grids
from .role_seams import _role_mesh,ROLES
from .contact_sources import surface_fingerprint,mapping_fingerprint


def merged_role_error_envelope(surfaces, *, target_mm,join_tolerance_mm,
                               max_depth=6,max_seed_cells=1024,max_triangles=20000):
    """Use the exact assembly used by screen_role_seams; never move source data.

    For corresponding barycentric points, |T_raw-T_merged| is at most the
    largest displacement of its three vertices. Add this to each raw bound.
    Float arithmetic is not interval-certified. No collision/solid/CAD gate.
    """
    alignment=conforming_role_grids(surfaces,target_mm=target_mm,join_tolerance_mm=join_tolerance_mm,
        max_depth=max_depth,max_seed_cells=max_seed_cells,max_triangles=max_triangles)
    result={'alignment':alignment,'mesh':None,'numeric_target_met':False,
        'error_applies_to':'merged_role_triangles','roundoff_certified':False,
        'continuous_surface_certified':False,'whole_geometry_verified':False,'contact_ready':False,
        'unchecked':['physical Span correspondence','seam curves between sampled rows',
                     'triangle validity, collision, periodic copies and containment','CAD/STEP final surfaces']}
    if not alignment['role_seam_input_ready']:
        return {**result,'status':alignment['status'],'reason':alignment['reason']}
    vertices,faces,roots,seams,roles=_role_mesh(alignment['grids'],join_tolerance_mm,max_triangles,100)
    try:
        with np.errstate(over='raise',invalid='raise'):
            displacement=np.linalg.norm(vertices-vertices[roots],axis=1)
            allowance=displacement[faces].max(axis=1)
            raw=np.concatenate([np.repeat(alignment['role_reports'][r]['cell_upper_mm'].ravel(),2) for r in ROLES])
            if len(raw)!=len(faces):raise ValueError('Triangle bounds do not match assembled face order.')
            merged=raw+allowance
            if not np.isfinite(merged).all():raise ValueError('Merged error bounds must be finite.')
    except FloatingPointError as exc:
        raise ValueError('Non-finite arithmetic in merged triangle error.') from exc
    unresolved=int(np.sum(merged>target_mm))
    report={**result,'status':'NUMERIC_TARGET_MET' if not unresolved else 'UNRESOLVED',
        'reason':'target' if not unresolved else 'merge_displacement_exceeds_error_budget',
        'numeric_target_met':unresolved==0,'unresolved_triangles':unresolved,'seams':seams,
        'mesh':{'vertices':vertices,'faces':roots[faces],'source_faces':faces,'vertex_roots':roots,
                'face_roles':roles},
        'unmerged_triangle_upper_mm':raw,'triangle_move_allowance_mm':allowance,
        'merged_triangle_upper_mm':merged,'max_unmerged_upper_mm':float(raw.max()),
        'max_vertex_move_mm':float(displacement.max()),'max_merged_upper_mm':float(merged.max())}
    report['source_fingerprints']={r:surface_fingerprint(surfaces[r]) for r in ROLES}
    report['mapping_fingerprint']=mapping_fingerprint(report)
    return report
