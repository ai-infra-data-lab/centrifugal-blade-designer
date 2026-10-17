"""Physical distances and normalized coordinates for the whole passage and blade rows."""
import numpy as np
from ..models.flow_path import StationType, ComponentRegion
from .meridional import calculate_meridional
from .meridional_segments import sample_meridional, ArcSegmentGeometry, _rotate

REGION_NAMES = ("Inlet", "Impeller", "Vaneless Diffuser / Gap", "Vaned Diffuser", "Outlet")

def validate_component_stations(parameters):
    if not isinstance(parameters.align_blade_stations_to_crossflow,bool):raise ValueError("Invalid station alignment mode.")
    stations = parameters.stations
    if len(stations) != 6 or [s.kind for s in stations] != list(StationType):
        raise ValueError("Stations must be INLET, IMP_LE, IMP_TE, DIF_LE, DIF_TE, OUTLET in that order.")
    values = np.asarray([s.m_flow_norm for s in stations],dtype=float)
    if not np.isfinite(values).all() or values[0] != 0 or values[-1] != 1 or np.any(np.diff(values)<=0):
        raise ValueError("Stations require finite 0 = INLET < IMP_LE < IMP_TE < DIF_LE < DIF_TE < OUTLET = 1.")
    return values

def component_regions(parameters):
    values = validate_component_stations(parameters)
    return [ComponentRegion(n,float(a),float(b)) for n,a,b in zip(REGION_NAMES,values[:-1],values[1:])]

def region_at(parameters,m_flow_norm):
    if not np.isfinite(m_flow_norm) or not 0 <= m_flow_norm <= 1:
        raise ValueError("Normalized flow coordinate must be in [0, 1].")
    regions=component_regions(parameters)
    return regions[min(np.searchsorted([r.end for r in regions],m_flow_norm,side="right"),4)].name

def normalize_distance(m,start,end):
    if not np.isfinite([start,end]).all() or end<=start or not np.isfinite(m).all():
        raise ValueError("Normalization requires finite distances and end > start.")
    return (np.asarray(m,dtype=float)-start)/(end-start)

def blade_row_coordinate(m,parameters,total_length,row="impeller"):
    validate_component_stations(parameters)
    le,te = (StationType.IMP_LE,StationType.IMP_TE) if row=="impeller" else (StationType.DIF_LE,StationType.DIF_TE) if row=="diffuser" else (None,None)
    if le is None:raise ValueError("Unknown blade row.")
    return normalize_distance(m,parameters.position(le)*total_length,parameters.position(te)*total_length)

def wall_tangent(wall,flow_parameter):
    distances=np.asarray(flow_parameter)*wall.length
    if hasattr(wall,'source_m'):
        indices=np.clip(np.searchsorted(wall.m,distances,side='right')-1,0,len(wall.m)-2)
        delta=np.column_stack((np.diff(wall.z),np.diff(wall.r)))
        return (delta/np.linalg.norm(delta,axis=1)[:,None])[indices]
    boundaries=np.r_[0,np.cumsum([s.length for s in wall.segments])]
    indices=np.minimum(np.searchsorted(boundaries,distances,side="right")-1,len(wall.segments)-1)
    result=np.empty(distances.shape+(2,))
    for i,segment in enumerate(wall.segments):
        mask=indices==i
        if isinstance(segment,ArcSegmentGeometry):
            angle=(distances[mask]-boundaries[i])/segment.length*segment.sweep_rad
            result[mask]=np.array([_rotate(segment.start_tangent,a) for a in np.atleast_1d(angle)]).reshape((-1,2))
        else:result[mask]=segment.start_tangent
    return result

def mean_meridional_line(hub,shroud,points=4001):
    # Common physical arc-fraction parameter, with both walls' joins included.
    joins=np.concatenate([np.cumsum([s.length for s in w.segments])/w.length for w in (hub,shroud)])
    flow_parameter=np.unique(np.r_[np.linspace(0,1,points),joins,0,1])
    if hasattr(hub,'source_m') or hasattr(shroud,'source_m'):
        # Sampled-wall joins can differ from the regular grid by roundoff only.
        flow_parameter=flow_parameter[np.r_[True,np.diff(flow_parameter)>1e-12]]
        flow_parameter[-1]=1.
    h=sample_meridional(hub,flow_parameter*hub.length)
    s=sample_meridional(shroud,flow_parameter*shroud.length)
    mean=(h+s)/2
    m,m_flow_norm=calculate_meridional(mean[:,1],mean[:,0])
    return flow_parameter,mean,m,m_flow_norm

def sample_mean_line(hub,shroud,m_flow_norm,points=4001):
    parameter,_,m,normalized=mean_meridional_line(hub,shroud,points)
    u=np.interp(np.asarray(m_flow_norm,dtype=float),normalized,parameter)
    h=sample_meridional(hub,u*hub.length);s=sample_meridional(shroud,u*shroud.length)
    derivative=(hub.length*wall_tangent(hub,u)+shroud.length*wall_tangent(shroud,u))/2
    speed=np.linalg.norm(derivative,axis=-1)
    if np.any(speed<1e-12):raise ValueError("Mean meridional tangent is undefined.")
    return u,(h+s)/2,derivative/speed[...,None],m[-1]
