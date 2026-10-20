"""Local source-triangle refinement without refitting or seam welding."""
import heapq
from copy import deepcopy
import numpy as np
from .contact_sources import source_triangle_patch,surface_fingerprint
from .surface_envelope import _control_net,_insert
from .surface_triangulation import _split,_cell
from .mesh_contacts import _nonnegative,_positive_int
from .error_aware_contacts import error_aware_mesh_contacts


def _restricted_net(surface,patch):
    knots,degrees,net=_control_net(surface);starts=[]
    for axis,bounds in enumerate((patch['span_range'],patch['xi_range'])):
        lo,hi=bounds;k=degrees[axis]
        if any(lo<x<hi for x in knots[axis]):raise ValueError('Source cell crosses an internal knot.')
        knots[axis],net=_insert(knots[axis],net,k,axis,{x:k+1 if x in (0,1) else k for x in bounds})
        starts.append(int(np.searchsorted(knots[axis],lo,side='right'))-1-k)
    i,j=starts;p,q=degrees
    return net[i:i+p+1,j:j+q+1].copy()


def refine_source_triangle(surface,patch,*,target_mm,max_depth=4,max_cells=256):
    """Cover exactly one recorded parameter triangle, including its boundary.

    Dyadic diagonal cells keep only their original ABC/ACD half. Other cells
    are inside the parent triangle. Independent leaves may have T junctions;
    their coverage/bounds support two-patch comparisons, not self topology.
    """
    _nonnegative(target_mm,'target_mm');_positive_int(max_cells,'max_cells')
    if type(max_depth) is not int or not 0<=max_depth<=8:raise ValueError('max_depth must be in [0,8].')
    try:
        bounds=np.array([*patch['span_range'],*patch['xi_range']],dtype=float)
        half=patch['diagonal_half']
        if (bounds.shape!=(4,) or not np.isfinite(bounds).all() or np.any(bounds<0) or np.any(bounds>1)
                or not bounds[0]<bounds[1] or not bounds[2]<bounds[3]
                or type(half) is not int or half not in (0,1)):raise ValueError('Invalid source triangle domain.')
    except (KeyError,TypeError) as exc:raise ValueError('Invalid source triangle domain.') from exc
    leaves={};queue=[];serial=0

    def add(net,box,depth,diagonal):
        nonlocal serial
        cell=_cell(net,box,depth);s0,s1,t0,t1=box
        xyz=surface.evaluate_grid([s0,s1],[t0,t1])
        actual=xyz[[0,1,1,0],[0,0,1,1]]
        cell.update(diagonal=diagonal,xyz=actual,
                    error=cell['upper']+float(np.linalg.norm(actual-cell['corners'],axis=1).max()))
        if not np.isfinite(cell['error']):raise ValueError('Local bounds must be finite.')
        leaves[serial]=cell
        if cell['error']>target_mm:heapq.heappush(queue,(-cell['error'],serial))
        serial+=1

    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            add(_restricted_net(surface,patch),tuple(bounds),0,True)
            while queue:
                _,key=heapq.heappop(queue);cell=leaves[key]
                if cell['depth']>=max_depth:continue
                extra=2 if cell['diagonal'] else 3
                if len(leaves)+extra>max_cells:break
                s0,s1,t0,t1=cell['bounds'];sm=s0+(s1-s0)/2;tm=t0+(t1-t0)/2
                if not s0<sm<s1 or not t0<tm<t1:raise ValueError('Source cell cannot be bisected in float64.')
                del leaves[key]
                for i,net_s in enumerate(_split(cell['net'],0)):
                    for j,net in enumerate(_split(net_s,1)):
                        if cell['diagonal'] and ((half==0 and i<j) or (half==1 and i>j)):continue
                        box=((s0,sm)[i],(sm,s1)[i],(t0,tm)[j],(tm,t1)[j])
                        add(net,box,cell['depth']+1,cell['diagonal'] and i==j)
    except FloatingPointError as exc:raise ValueError('Non-finite local refinement arithmetic.') from exc
    vertices=[];parameters=[];faces=[];errors=[];cells=[]
    for cell in sorted(leaves.values(),key=lambda c:c['bounds']):
        s0,s1,t0,t1=cell['bounds'];offset=len(vertices)
        vertices.extend(cell['xyz']);parameters.extend(((s0,t0),(s1,t0),(s1,t1),(s0,t1)))
        local=[(0,1,2),(0,2,3)]
        if cell['diagonal']:local=[local[half]]
        faces.extend([tuple(offset+x for x in face) for face in local]);errors.extend([cell['error']]*len(local))
        cells.append({'span_range':[s0,s1],'xi_range':[t0,t1],'diagonal':cell['diagonal'],
                      'depth':cell['depth'],'upper_mm':cell['error']})
    met=all(e<=target_mm for e in errors)
    return {'status':'NUMERIC_TARGET_MET' if met else 'UNRESOLVED','numeric_target_met':met,
            'parent_patch':dict(patch),'vertices':np.array(vertices),'faces':np.array(faces,dtype=np.int64),
            'parameter_vertices':np.array(parameters),'triangle_upper_mm':np.array(errors),'cells':cells,
            'cell_count':len(cells),'max_upper_mm':max(errors),'max_depth':max_depth,'max_cells':max_cells,
            'roundoff_certified':False,'contact_ready':False,'whole_geometry_verified':False}


def refine_contact_pair(surfaces,envelope,first_face,second_face,*,target_mm,clearance_mm,
                        area_epsilon_mm2,max_depth=4,max_cells=256,max_work=500000,max_records=100):
    """Re-evaluate one pair against the same recorded source surfaces only."""
    _nonnegative(clearance_mm,'clearance_mm');_nonnegative(area_epsilon_mm2,'area_epsilon_mm2')
    _positive_int(max_work,'max_work');_positive_int(max_records,'max_records')
    patches=[source_triangle_patch(envelope,i) for i in (first_face,second_face)]
    if first_face==second_face:raise ValueError('Two distinct source triangles are required.')
    snapshots={}
    for patch in patches:
        role=patch['role']
        try:snapshots[role]=deepcopy(surfaces[role])
        except (KeyError,TypeError) as exc:raise ValueError('Selected source roles are required.') from exc
        if surface_fingerprint(snapshots[role])!=envelope.get('source_fingerprints',{}).get(role):
            raise ValueError('Source surface changed or lacks a recorded identity.')
    refined=[refine_source_triangle(snapshots[p['role']],p,target_mm=target_mm,
                                    max_depth=max_depth,max_cells=max_cells) for p in patches]
    a,b=refined
    report=error_aware_mesh_contacts(a['vertices'],a['faces'],a['triangle_upper_mm'],
        b['vertices'],b['faces'],b['triangle_upper_mm'],clearance_mm=clearance_mm,
        area_epsilon_mm2=area_epsilon_mm2,max_work=max_work,max_records=max_records,max_triangles=2*max_cells)
    return {'status':report['status'],'contact_report':report,'patches':patches,'refined':refined,
            'source_identity_checked':True,'source_basis':'original_unmerged_splines',
            'refinement_target_met':all(r['numeric_target_met'] for r in refined),
            'whole_geometry_verified':False,'continuous_surface_certified':False,'roundoff_certified':False}
