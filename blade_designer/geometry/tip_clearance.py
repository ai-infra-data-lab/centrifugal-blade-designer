"""Open-impeller Tip from casing-normal clearance, independent of Qt/I/O.

Shroud remains the fixed casing. LE/TE reference casing arclength; clearance
is linear between these distances and constant outside, including edge caps.
The Hub-TE cutoff cylinder remains unchanged.
"""
from copy import deepcopy
import numpy as np
from scipy.optimize import brentq
from scipy.spatial import cKDTree
from ..models.geometry_3d import TipMeridionalGeometry
from ..models.parameters import EdgeType,TipClearanceParameters
from ..models.validation import is_finite_number
from .meridional_segments import sample_meridional
from .flow_path import wall_tangent
from .blade_edge import blade_wall_parameters, edge_endpoints
from .span import interpolate_span_position


def has_tip_clearance(params):
    c=params.tip_clearance
    if c is None:return False
    if not isinstance(c,TipClearanceParameters) or any(not is_finite_number(v) or v<0 for v in (c.le_mm,c.te_mm)):
        raise ValueError('Tip clearance LE/TE must be finite and >= 0 mm.')
    return c.le_mm>0 or c.te_mm>0


def _frame(hub,casing,distances):
    u=np.asarray(distances)/casing.length
    points=sample_meridional(casing,np.asarray(distances))
    tangents=wall_tangent(casing,u)
    normal=np.column_stack((-tangents[:,1],tangents[:,0]))
    toward=sample_meridional(hub,u*hub.length)-points
    projection=np.einsum('ij,ij->i',normal,toward)
    if np.any(np.abs(projection)<1e-9):
        raise ValueError('Tip clearance: casing inward normal is ambiguous.')
    if np.any(projection>0) and np.any(projection<0):
        raise ValueError('Tip clearance: casing inward normal changes sides.')
    normal*=np.sign(projection)[:,None]
    return points,normal,np.abs(projection)


def _check_open_curve(points):
    starts,ends=points[:-1],points[1:]
    steps=ends-starts
    half=np.linalg.norm(steps,axis=1)/2
    if np.any(half<=1e-12):raise ValueError('Tip clearance: collapsed Tip path.')
    pairs=cKDTree((starts+ends)/2).query_pairs(2*float(max(half)),output_type='ndarray')
    if not len(pairs):return
    i,j=pairs[pairs[:,1]-pairs[:,0]>1].T
    cross=lambda a,b:a[:,0]*b[:,1]-a[:,1]*b[:,0]
    a,b,c,d=starts[i],ends[i],starts[j],ends[j]
    o1,o2=cross(b-a,c-a),cross(b-a,d-a)
    o3,o4=cross(d-c,a-c),cross(d-c,b-c)
    boxes=np.all(np.maximum(np.minimum(a,b),np.minimum(c,d))<=np.minimum(np.maximum(a,b),np.maximum(c,d))+1e-10,axis=1)
    if np.any(boxes & (o1*o2<=0) & (o3*o4<=0)):
        raise ValueError('Tip clearance: Tip meridional self-intersection.')


def make_tip_geometry(params,hub,casing):
    if not has_tip_clearance(params):return None
    settings=params.tip_clearance;edges=params.impeller_edges
    le=edges.leading_edge.shroud_m_flow_norm*casing.length
    te=edges.trailing_edge.shroud_m_flow_norm*casing.length
    # Match the actual constant-D TE, rather than an unused Shroud TE fraction.
    if params.sections[-1].edge_parameters.te_type==EdgeType.CUTOFF:
        radius=float(edge_endpoints(edges.trailing_edge,hub,casing)[0,1])
        def residual(distance):
            point,normal,_=_frame(hub,casing,np.array([distance]))
            return float((point+settings.te_mm*normal)[0,1]-radius)
        grid=np.unique(np.r_[np.linspace(le,casing.length,513),te])
        values=np.array([residual(v) for v in grid])
        roots=[]
        for i in np.flatnonzero(values[:-1]*values[1:]<=0):
            if abs(values[i])<1e-10:roots.append(grid[i])
            elif values[i]!=values[i+1]:roots.append(brentq(residual,grid[i],grid[i+1],xtol=1e-11))
        if not roots:raise ValueError('Tip clearance: no Tip intersection with the Hub TE cutoff cylinder.')
        te=float(min(roots,key=lambda v:abs(v-te)))
    if te<=le+1e-9:raise ValueError('Tip clearance: Tip TE must follow LE.')
    joins=np.r_[0.,np.cumsum([s.length for s in casing.segments])]
    distances=np.unique(np.r_[np.linspace(0,casing.length,params.resolution.wall_points),joins,le,te])
    points,normals,available=_frame(hub,casing,distances)
    clearance=np.interp(distances,[le,te],[settings.le_mm,settings.te_mm])
    if np.any(clearance>=available-1e-8):
        raise ValueError('Tip clearance reaches/exceeds the available Hub–casing width.')
    tip=points+clearance[:,None]*normals
    if not np.isfinite(tip).all() or np.any(tip[:,1]<=0):
        raise ValueError('Tip clearance requires finite positive Tip radius.')
    direction=wall_tangent(casing,(distances[1:]+distances[:-1])/2/casing.length)
    if np.any(np.einsum('ij,ij->i',np.diff(tip,axis=0),direction)<=0):
        raise ValueError('Tip clearance produces a cusp or reversed Tip path.')
    _check_open_curve(tip)
    return TipMeridionalGeometry(distances,tip[:,0],tip[:,1],clearance,float(le),float(te))


def row_wall_parameters(edges,flow,geometry):
    if geometry.tip is None:return blade_wall_parameters(edges,flow)
    local=deepcopy(edges)
    local.trailing_edge.shroud_m_flow_norm=geometry.tip.te_casing_m/geometry.shroud.length
    return blade_wall_parameters(local,flow)


def blade_span_wall(geometry,span,hub_parameter,tip_parameter):
    if geometry.tip is None:
        return interpolate_span_position(geometry.hub,geometry.shroud,span,hub_parameter,tip_parameter)
    tip=geometry.tip
    distances=np.asarray(tip_parameter)*geometry.shroud.length
    zr=np.column_stack([np.interp(distances,tip.casing_m,v) for v in (tip.z,tip.r)])
    return (1-span)*sample_meridional(geometry.hub,np.asarray(hub_parameter)*geometry.hub.length)+span*zr
