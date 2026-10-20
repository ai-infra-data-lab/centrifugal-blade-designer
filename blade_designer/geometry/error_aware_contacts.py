"""Read-only separation screening of two meshes with positional error bounds.

Bounds belong to corresponding source patches, not just sampled points. They
must include vertex merging. This float diagnostic does not certify rounding,
continuous surfaces, containment, self adjacency or final CAD geometry.
"""
import numpy as np
from .mesh_contacts import _mesh, _nonnegative, _positive_int, _tree, _pairs


def _errors(values, count):
    values=np.asarray(values)
    if (values.shape!=(count,) or not np.isrealobj(values)
            or not np.issubdtype(values.dtype,np.number)
            or not np.isfinite(values).all() or np.any(values<0)):
        raise ValueError('Error bounds must be one finite nonnegative real value per triangle.')
    result=values.astype(float,copy=True)
    if not np.isfinite(result).all():raise ValueError('Error bounds must fit float64.')
    return result


def _separation_lower(a,b):
    """Maximum unit-axis projection gap, a lower bound, NOT exact distance."""
    b=b-a[0];a=a-a[0]
    ea=np.roll(a,-1,axis=0)-a;eb=np.roll(b,-1,axis=0)-b
    ea=ea/np.linalg.norm(ea,axis=1)[:,None]
    eb=eb/np.linalg.norm(eb,axis=1)[:,None]
    na=np.cross(ea[0],ea[1]);nb=np.cross(eb[0],eb[1])
    axes=np.concatenate((np.eye(3),[na,nb],
                         np.cross(ea[:,None,:],eb[None,:,:]).reshape(-1,3),
                         np.cross(na,ea),np.cross(nb,eb)))
    norms=np.linalg.norm(axes,axis=1)
    axes=axes[norms>0]/norms[norms>0,None]
    pa=a@axes.T;pb=b@axes.T
    gap=np.maximum(pb.min(axis=0)-pa.max(axis=0),pa.min(axis=0)-pb.max(axis=0))
    return max(0.,float(gap.max()))


def error_aware_mesh_contacts(vertices,faces,error_upper_mm,
                              second_vertices,second_faces,second_error_upper_mm,*,
                              clearance_mm,area_epsilon_mm2,max_work=500000,
                              max_records=100,max_triangles=20000):
    """Screen two independent meshes; each supplied bound covers its source patch.

    Strict separation requires lower > error_a + error_b + clearance. Equality
    is uncertain. Expanded AABBs accelerate only this same conservative test.
    A triangle contact is a candidate, never proof of source-surface contact.
    Work/record limits or any degenerate face prevent NUMERIC_SEPARATED.
    No faces are excluded by matching vertex IDs across the two meshes.
    """
    _nonnegative(clearance_mm,'clearance_mm')
    _nonnegative(area_epsilon_mm2,'area_epsilon_mm2')
    for value,name in ((max_work,'max_work'),(max_records,'max_records'),(max_triangles,'max_triangles')):
        _positive_int(value,name)
    va,fa=_mesh(vertices,faces,max_triangles)
    vb,fb=_mesh(second_vertices,second_faces,max_triangles)
    stats={'work_units':0,'node_pair_tests':0,'triangle_pair_tests':0,'stop_reason':None}
    records=[];contacts=0;uncertain=0;separated=0
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            errors=[_errors(error_upper_mm,len(fa)),_errors(second_error_upper_mm,len(fb))]
            triangles=[va[fa],vb[fb]]
            areas=[np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)/2 for t in triangles]
            if not all(np.isfinite(a).all() for a in areas):raise ValueError('Triangle areas must be finite.')
            degenerate=[np.flatnonzero(a<=area_epsilon_mm2) for a in areas]
            valid=[np.flatnonzero(a>area_epsilon_mm2) for a in areas]
            # Coordinate-wise expansion encloses the Euclidean error ball.
            margins=[(e+clearance_mm/2)[:,None] for e in errors]
            lows=[t.min(axis=1)-m for t,m in zip(triangles,margins)]
            highs=[t.max(axis=1)+m for t,m in zip(triangles,margins)]
            if all(len(v) for v in valid):
                trees=[_tree(lo,hi,ids) for lo,hi,ids in zip(lows,highs,valid)]
                for i,j in _pairs(*trees,False,0.,max_work,stats):
                    lower=_separation_lower(triangles[0][i],triangles[1][j])
                    budget=float(errors[0][i]+errors[1][j]+clearance_mm)
                    if not np.isfinite(lower+budget):raise ValueError('Separation arithmetic must be finite.')
                    if lower>budget:
                        separated+=1
                        continue
                    kind='TRIANGLE_CONTACT_CANDIDATE' if lower==0 else 'UNCERTAIN'
                    contacts+=int(lower==0);uncertain+=int(lower>0)
                    records.append({'first_face':i,'second_face':j,'kind':kind,
                                    'projection_lower_mm':lower,'required_lower_mm':budget})
                    if len(records)>=max_records:
                        stats['stop_reason']='max_records'
                        break
    except FloatingPointError as exc:
        raise ValueError('Non-finite arithmetic in error-aware screening.') from exc
    complete=stats['stop_reason'] is None and not any(len(d) for d in degenerate)
    clear=complete and not records
    status=('CONTACT_CANDIDATES_FOUND' if contacts else 'INCOMPLETE' if not complete
            else 'UNCERTAIN' if uncertain else 'NUMERIC_SEPARATED')
    return {'status':status,'numeric_separated':bool(clear),'scan_complete':bool(complete),
            'records':records,'contact_candidates':contacts,'uncertain_pairs':uncertain,
            'explicitly_separated_pairs':separated,**stats,
            'first_triangles':len(fa),'second_triangles':len(fb),
            'first_degenerate_faces':degenerate[0].tolist(),'second_degenerate_faces':degenerate[1].tolist(),
            'clearance_mm':float(clearance_mm),'area_epsilon_mm2':float(area_epsilon_mm2),
            'error_bounds_assumed_valid':True,'self_adjacency_checked':False,
            'continuous_surface_certified':False,'roundoff_certified':False,
            'containment_checked':False,'whole_geometry_verified':False}
