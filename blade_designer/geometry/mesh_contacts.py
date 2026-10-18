"""Numerical contact screening of triangle approximations, never a CAD gate.

SAT includes coplanar axes. Nonzero tolerance is a projection-space allowance,
not a Euclidean clearance measurement. Float rounding is not certified.
Default self checks omit faces sharing 1 or 2 vertex IDs. Optional shared-edge
and vertex classification distinguish expected joins and overlap candidates.
No surface-to-mesh error bound, containment or continuous-surface guarantee.
"""
from dataclasses import dataclass
from numbers import Real
import numpy as np
from .mesh_adjacency import _edge_relation, _nonmanifold_edges
from .mesh_vertex_adjacency import _vertex_relation, _vertex_links


def _nonnegative(value, name):
    if (isinstance(value,(bool,np.bool_)) or not isinstance(value,Real)
            or not np.isfinite(value) or value < 0):
        raise ValueError(name+' must be finite and nonnegative.')


def _positive_int(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name+' must be a positive integer.')


def _mesh(vertices, faces, max_triangles):
    v=np.asarray(vertices)
    f=np.asarray(faces)
    if (v.ndim!=2 or v.shape[1]!=3 or len(v)<3 or not np.isrealobj(v)
            or not np.issubdtype(v.dtype,np.number) or not np.isfinite(v).all()):
        raise ValueError('Mesh vertices must be finite real Nx3 XYZ values.')
    if (f.ndim!=2 or f.shape[1]!=3 or not 0<len(f)<=max_triangles
            or not np.issubdtype(f.dtype,np.integer) or np.any(f<0) or np.any(f>=len(v))):
        raise ValueError('Mesh faces must be nonempty integer triangles within vertex/max_triangles limits.')
    try:
        with np.errstate(over='raise',invalid='raise'):
            vertices=v.astype(float,copy=True)
    except FloatingPointError as exc:
        raise ValueError('Mesh vertices must fit finite float64 values.') from exc
    return vertices, f.astype(np.int64,copy=True)


@dataclass
class _Node:
    low: np.ndarray
    high: np.ndarray
    ids: np.ndarray
    children: tuple = ()


def _tree(low, high, ids):
    node=_Node(low[ids].min(axis=0),high[ids].max(axis=0),ids)
    if len(ids)>8:
        centers=low[ids]/2+high[ids]/2
        axis=int(np.argmax(np.ptp(centers,axis=0)))
        ordered=ids[np.argsort(centers[:,axis],kind='stable')]
        half=len(ids)//2
        node.children=(_tree(low,high,ordered[:half]),_tree(low,high,ordered[half:]))
    return node


def _overlaps(a_low, a_high, b_low, b_high, tolerance):
    return bool(np.all(a_low<=b_high+tolerance) and np.all(b_low<=a_high+tolerance))


def _pairs(first, second, self_check, tolerance, max_work, stats):
    stack=[(first,second)]
    while stack:
        if stats['work_units']>=max_work:
            stats['stop_reason']='max_work'
            return
        a,b=stack.pop();stats['work_units']+=1;stats['node_pair_tests']+=1
        if not _overlaps(a.low,a.high,b.low,b.high,tolerance):continue
        if not a.children and not b.children:
            for i in a.ids:
                for j in b.ids:
                    if self_check and a is b and i>=j:continue
                    if stats['work_units']>=max_work:
                        stats['stop_reason']='max_work'
                        return
                    stats['work_units']+=1;stats['triangle_pair_tests']+=1
                    yield (min(int(i),int(j)),max(int(i),int(j))) if self_check else (int(i),int(j))
        elif self_check and a is b:
            left,right=a.children
            stack.extend(((right,right),(left,right),(left,left)))
        elif a.children and (not b.children or len(a.ids)>=len(b.ids)):
            stack.extend((child,b) for child in reversed(a.children))
        else:
            stack.extend((a,child) for child in reversed(b.children))


def _sat_contact(a, b, tolerance):
    # Translate before projections to reduce dependence on a large common origin.
    b=b-a[0];a=a-a[0]
    ea=np.roll(a,-1,axis=0)-a;eb=np.roll(b,-1,axis=0)-b
    ea=ea/np.linalg.norm(ea,axis=1)[:,None]
    eb=eb/np.linalg.norm(eb,axis=1)[:,None]
    na=np.cross(ea[0],ea[1]);nb=np.cross(eb[0],eb[1])
    axes=np.concatenate(([na,nb],np.cross(ea[:,None,:],eb[None,:,:]).reshape(-1,3),
                         np.cross(na,ea),np.cross(nb,eb)))
    norms=np.linalg.norm(axes,axis=1)
    axes=axes[norms>0]/norms[norms>0,None]
    pa=a@axes.T;pb=b@axes.T
    return not bool(np.any(pa.max(axis=0)<pb.min(axis=0)-tolerance)
                    or np.any(pb.max(axis=0)<pa.min(axis=0)-tolerance))


def mesh_contacts(vertices, faces, second_vertices=None, second_faces=None, *,
                  tolerance_mm, area_epsilon_mm2, max_work=500000,
                  max_contacts=100, max_triangles=20000, check_shared_edges=False,
                  check_shared_vertices=False):
    """Read-only BVH/SAT report; omitted second mesh means nonlocal self check.

    Degenerate triangles are listed and not tested. Work/contact limits return
    incomplete evidence, never a clean result. IDs refer to original faces.
    Boundary contact and coplanar overlap are included, with no penetration
    depth or distinction between touching and crossing. Closed-solid nesting
    without surface contact is outside this test.
    check_shared_edges opts into local edge-neighbor classification and >2-face
    edge incidence diagnostics. check_shared_vertices additionally checks vertex-only
    neighbors and links, and requires check_shared_edges=True. Both default off.
    """
    _nonnegative(tolerance_mm,'tolerance_mm')
    _nonnegative(area_epsilon_mm2,'area_epsilon_mm2')
    for value,name in ((max_work,'max_work'),(max_contacts,'max_contacts'),(max_triangles,'max_triangles')):
        _positive_int(value,name)
    self_check=second_vertices is None and second_faces is None
    if type(check_shared_edges) is not bool or (check_shared_edges and not self_check):
        raise ValueError('check_shared_edges must be bool and only enabled for a self check.')
    if type(check_shared_vertices) is not bool or (check_shared_vertices and (not self_check or not check_shared_edges)):
        raise ValueError('check_shared_vertices must be bool and requires a shared-edge self check.')
    if (second_vertices is None)!=(second_faces is None):
        raise ValueError('Both second mesh vertices and faces must be supplied.')
    va,fa=_mesh(vertices,faces,max_triangles)
    vb,fb=(va,fa) if self_check else _mesh(second_vertices,second_faces,max_triangles)
    stats={'work_units':0,'node_pair_tests':0,'triangle_pair_tests':0,'stop_reason':None}
    contacts=[];kinds=[];excluded=0;candidates=0
    adjacency={'enabled':check_shared_edges,'checked_shared_edge_pairs':0,
               'expected_shared_edge_pairs':0,'overlap_candidates':0,
               'unresolved_count':0,'unresolved_examples':[],
               'vertex_neighbor_pairs_excluded':0,'nonmanifold_edge_count':None,
               'nonmanifold_edge_examples':[],'vertex_links_checked':False}
    vertex_adjacency={'enabled':check_shared_vertices,'checked_vertex_pairs':0,'expected_vertex_pairs':0,
                      'overlap_candidates':0,'unresolved_count':0,'unresolved_examples':[],
                      'links_checked':check_shared_vertices,'nonmanifold_vertex_count':None,
                      'nonmanifold_vertex_examples':[]}
    adjacency['vertex_links_checked']=check_shared_vertices
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            triangles=[va[fa],vb[fb]]
            lows=[t.min(axis=1) for t in triangles];highs=[t.max(axis=1) for t in triangles]
            areas=[np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)/2 for t in triangles]
            if not all(np.isfinite(a).all() for a in areas):raise ValueError('Triangle areas must be finite.')
            degenerate=[np.flatnonzero(a<=area_epsilon_mm2) for a in areas]
            valid=[np.flatnonzero(a>area_epsilon_mm2) for a in areas]
            if check_shared_edges:
                count,examples=_nonmanifold_edges(fa,valid[0],max_contacts)
                adjacency['nonmanifold_edge_count']=count
                adjacency['nonmanifold_edge_examples']=examples
            if check_shared_vertices:
                count,examples=_vertex_links(fa,valid[0],max_contacts)
                vertex_adjacency['nonmanifold_vertex_count']=count
                vertex_adjacency['nonmanifold_vertex_examples']=examples
            if all(len(v) for v in valid):
                first=_tree(lows[0],highs[0],valid[0])
                second=first if self_check else _tree(lows[1],highs[1],valid[1])
                for i,j in _pairs(first,second,self_check,tolerance_mm,max_work,stats):
                    shared=len(set(fa[i]) & set(fa[j])) if self_check else 0
                    if (shared==1 and not check_shared_vertices) or (shared==2 and not check_shared_edges):
                        excluded+=1
                        if shared==1:adjacency['vertex_neighbor_pairs_excluded']+=1
                        continue
                    if shared==1:
                        vertex_adjacency['checked_vertex_pairs']+=1
                        relation=_vertex_relation(va,fa[i],fa[j],tolerance_mm)
                        if relation=='EXPECTED_VERTEX':
                            vertex_adjacency['expected_vertex_pairs']+=1
                            continue
                        if relation=='UNRESOLVED':
                            vertex_adjacency['unresolved_count']+=1
                            if len(vertex_adjacency['unresolved_examples'])<max_contacts:
                                vertex_adjacency['unresolved_examples'].append([i,j])
                            continue
                        contact=True;kind='shared_vertex_overlap_candidate'
                        vertex_adjacency['overlap_candidates']+=1
                    elif shared==2:
                        adjacency['checked_shared_edge_pairs']+=1
                        relation=_edge_relation(va,fa[i],fa[j],tolerance_mm)
                        if relation=='EXPECTED_EDGE':
                            adjacency['expected_shared_edge_pairs']+=1
                            continue
                        if relation=='UNRESOLVED':
                            adjacency['unresolved_count']+=1
                            if len(adjacency['unresolved_examples'])<max_contacts:
                                adjacency['unresolved_examples'].append([i,j])
                            continue
                        contact=True;kind='shared_edge_overlap_candidate'
                        adjacency['overlap_candidates']+=1
                    else:
                        if not _overlaps(lows[0][i],highs[0][i],lows[1][j],highs[1][j],tolerance_mm):continue
                        candidates+=1
                        contact=_sat_contact(triangles[0][i],triangles[1][j],tolerance_mm)
                        kind='triangle_contact_candidate'
                    if contact:
                        contacts.append([i,j])
                        kinds.append(kind)
                        if len(contacts)>=max_contacts:
                            stats['stop_reason']='max_contacts'
                            break
    except FloatingPointError as exc:
        raise ValueError('Non-finite arithmetic in mesh contact screening.') from exc
    adjacency['unresolved_examples_truncated']=adjacency['unresolved_count']>len(adjacency['unresolved_examples'])
    vertex_adjacency['unresolved_examples_truncated']=vertex_adjacency['unresolved_count']>len(vertex_adjacency['unresolved_examples'])
    complete=(stats['stop_reason'] is None and not any(len(v) for v in degenerate)
              and not adjacency['unresolved_count'] and not adjacency['nonmanifold_edge_count']
              and not vertex_adjacency['unresolved_count'] and not vertex_adjacency['nonmanifold_vertex_count'])
    return {'contact_pairs':contacts,'contact_kinds':kinds,'contact_count':len(contacts),'adjacency':adjacency,
            'vertex_adjacency':vertex_adjacency,
            'status':'CONTACT_CANDIDATES_FOUND' if contacts else 'NO_CONTACT_OBSERVED' if complete else 'INCOMPLETE',
            'scan_complete':bool(complete),'self_check':self_check,
            'first_triangles':len(fa),'second_triangles':len(fb),
            'first_degenerate_faces':degenerate[0].tolist(),'second_degenerate_faces':degenerate[1].tolist(),
            'adjacent_pairs_excluded':excluded,'aabb_candidates':candidates,**stats,
            'tolerance_mm':float(tolerance_mm),'area_epsilon_mm2':float(area_epsilon_mm2),
            'continuous_surface_certified':False,'roundoff_certified':False,
            'containment_checked':False}


def grid_mesh(grid):
    """Fixed-diagonal triangulation of an explicit XYZ tensor sample grid."""
    xyz=np.asarray(grid)
    if (xyz.ndim!=3 or xyz.shape[2]!=3 or min(xyz.shape[:2])<2
            or not np.isrealobj(xyz) or not np.issubdtype(xyz.dtype,np.number) or not np.isfinite(xyz).all()):
        raise ValueError('Surface grid must be finite real SxTx3 with S,T >= 2.')
    ids=np.arange(xyz.shape[0]*xyz.shape[1]).reshape(xyz.shape[:2])
    a=ids[:-1,:-1].ravel();b=ids[1:,:-1].ravel();c=ids[1:,1:].ravel();d=ids[:-1,1:].ravel()
    faces=np.stack((np.column_stack((a,b,c)),np.column_stack((a,c,d))),axis=1).reshape(-1,3)
    try:
        with np.errstate(over='raise',invalid='raise'):
            vertices=xyz.astype(float,copy=True).reshape(-1,3)
    except FloatingPointError as exc:
        raise ValueError('Surface grid must fit finite float64 values.') from exc
    return vertices,faces
