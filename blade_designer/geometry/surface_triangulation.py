"""Adaptive local triangle error envelopes for a reference tensor spline.

Exact-arithmetic convex-hull argument, evaluated with uncertified float64.
Independent cells may have T junctions: this is NOT a contact-ready mesh.
"""
from collections import Counter
import heapq
import numpy as np
from .surface_envelope import _control_net,_insert
from .mesh_contacts import _nonnegative,_positive_int


def _split(net,axis):
    values=np.moveaxis(net,axis,0).copy();left=[values[0]];right=[values[-1]]
    while len(values)>1:
        values=values[:-1]/2+values[1:]/2
        left.append(values[0]);right.append(values[-1])
    return np.moveaxis(np.array(left),0,axis),np.moveaxis(np.array(right[::-1]),0,axis)


def _triangles(corners,u,v):
    a,b,c,d=corners
    return (a+u*(b-a)+v*(c-b) if u>=v else a+v*(d-a)+u*(c-d))


def _cell(net,bounds,depth):
    p,q=np.array(net.shape[:2])-1
    a,b,c,d=net[0,0],net[-1,0],net[-1,-1],net[0,-1]
    u=np.linspace(0,1,p+1)[:,None,None];v=np.linspace(0,1,q+1)[None,:,None]
    bilinear=(1-u)*(1-v)*a+u*(1-v)*b+u*v*c+(1-u)*v*d
    # Degree-elevated bilinear poles; bound S-L then L-triangle separately.
    upper=float(np.max(np.linalg.norm(net-bilinear,axis=-1))+
                np.linalg.norm(a-b+c-d)/4)
    if not np.isfinite(upper):raise ValueError('Triangle envelope must be finite.')
    return {'net':net,'bounds':bounds,'depth':depth,'upper':upper,'corners':np.array([a,b,c,d])}


def adaptive_triangle_envelope(surface, *, target_mm,max_depth=6,max_cells=4096):
    """Refine worst complete Bezier cells; never refit or change the surface.

    Norm(S-L) <= max Bernstein residual pole norm. For bilinear L and the
    00--11 diagonal triangles, Norm(L-T) <= Norm(A-B+C-D)/4.
    This gives a bidirectional correspondence bound in exact arithmetic only.
    Target status is numerical evidence, not a manufacturing/mesh certificate.
    """
    _nonnegative(target_mm,'target_mm');_positive_int(max_cells,'max_cells')
    if type(max_depth) is not int or not 0<=max_depth<=12:
        raise ValueError('max_depth must be an integer in [0,12].')
    knots,degrees,net=_control_net(surface)
    targets=[]
    for t,k in zip(knots,degrees):
        if any(n>k for x,n in Counter(t).items() if 0<x<1):
            raise ValueError('Discontinuous internal knots are unsupported.')
        targets.append({x:k if 0<x<1 else k+1 for x in np.unique(t)})
    breaks=[np.array(sorted(t)) for t in targets]
    initial=(len(breaks[0])-1)*(len(breaks[1])-1)
    if initial>max_cells:raise ValueError('Initial Bezier cells exceed max_cells.')
    leaves={};queue=[];serial=0
    def add(cell):
        nonlocal serial
        leaves[serial]=cell
        if cell['upper']>target_mm:heapq.heappush(queue,(-cell['upper'],serial))
        serial+=1
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            for axis,target in enumerate(targets):
                knots[axis],net=_insert(knots[axis],net,degrees[axis],axis,target)
            p,q=degrees
            for i,(u0,u1) in enumerate(zip(breaks[0],breaks[0][1:])):
                for j,(v0,v1) in enumerate(zip(breaks[1],breaks[1][1:])):
                    add(_cell(net[i*p:i*p+p+1,j*q:j*q+q+1],(u0,u1,v0,v1),0))
            while queue:
                _,key=heapq.heappop(queue);cell=leaves[key]
                if cell['depth']>=max_depth:continue
                if len(leaves)+3>max_cells:break
                u0,u1,v0,v1=cell['bounds'];um=u0+(u1-u0)/2;vm=v0+(v1-v0)/2
                if not u0<um<u1 or not v0<vm<v1:
                    raise ValueError('Cell cannot be refined at floating-point precision.')
                del leaves[key]
                for half,lo,hi in zip(_split(cell['net'],0),(u0,um),(um,u1)):
                    for child,low,high in zip(_split(half,1),(v0,vm),(vm,v1)):
                        add(_cell(child,(lo,hi,low,high),cell['depth']+1))
            cells=[]
            for cell in sorted(leaves.values(),key=lambda c:c['bounds']):
                u0,u1,v0,v1=cell['bounds'];query=np.array([0.,.5,1.])
                xyz=surface.evaluate_grid(u0+(u1-u0)*query,v0+(v1-v0)*query)
                sample=max(np.linalg.norm(xyz[i,j]-_triangles(cell['corners'],u,v))
                           for i,u in enumerate(query) for j,v in enumerate(query))
                if not np.isfinite(sample):raise ValueError('Triangle error samples must be finite.')
                met=cell['upper']<=target_mm and sample<=target_mm
                cells.append({'span_range':[float(u0),float(u1)],'xi_range':[float(v0),float(v1)],
                    'depth':cell['depth'],'upper_mm':cell['upper'],'sample_max_mm':float(sample),
                    'sample_exceeds_upper':bool(sample>cell['upper']),
                    'reason':('target' if met else 'sample_above_target' if cell['upper']<=target_mm
                              else 'max_depth' if cell['depth']>=max_depth else 'max_cells'),
                    'numeric_target_met':bool(met),'corners_xyz':cell['corners'].tolist()})
    except FloatingPointError as exc:
        raise ValueError('Non-finite arithmetic in triangle envelope.') from exc
    unresolved=sum(not c['numeric_target_met'] for c in cells)
    return {'status':'NUMERIC_TARGET_MET' if not unresolved else 'UNRESOLVED',
        'cells':cells,'cell_count':len(cells),'triangle_count':2*len(cells),'initial_cells':initial,
        'unresolved_cells':unresolved,'target_mm':float(target_mm),
        'max_upper_mm':max(c['upper_mm'] for c in cells),
        'sample_max_mm':max(c['sample_max_mm'] for c in cells),
        'sample_upper_violations':sum(c['sample_exceeds_upper'] for c in cells),
        'max_depth':max_depth,'max_cells':max_cells,'depth_reached':max(c['depth'] for c in cells),
        'roundoff_certified':False,'contact_ready':False,'whole_geometry_verified':False,
        'unchecked':['conforming mesh across adaptive cells and roles','surface regularity and self contact',
                     'periodic copies, containment and other blade sets','CAD/STEP final surfaces']}
