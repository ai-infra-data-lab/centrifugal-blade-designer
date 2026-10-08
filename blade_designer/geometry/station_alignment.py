"""Match blade stations to finite-wall cross-flow cuts, without exporter conventions."""
import numpy as np
from ..models.meridional import ArcSegmentGeometry
from ..models.flow_path import StationType
from .meridional_segments import _contains,sample_meridional
from .flow_path import sample_mean_line
from .flow_area import crossflow_pair

def wall_distance(wall,point):
    offset=0.
    for segment in wall.segments:
        if _contains(segment,point):
            if isinstance(segment,ArcSegmentGeometry):
                a=segment.start.zr-segment.center.zr;b=point-segment.center.zr
                angle=np.arctan2(a[0]*b[1]-a[1]*b[0],a@b)
                if abs(angle)<1e-12:angle=0.
                if segment.clockwise:angle=(-angle)%(2*np.pi)
                else:angle=angle%(2*np.pi)
                distance=segment.radius*angle
            else:distance=float((point-segment.start.zr)@segment.start_tangent)
            return offset+np.clip(distance,0,segment.length)
        offset+=segment.length
    raise ValueError("Blade station is not on its meridional wall.")

def blade_station_wall_parameters(hub,shroud,flow_path,m_flow_norm,mean_points=4001):
    le,te=[flow_path.position(k) for k in (StationType.IMP_LE,StationType.IMP_TE)]
    u,mean,tangent,_=sample_mean_line(hub,shroud,np.array([le,te]),mean_points)
    h=sample_meridional(hub,u*hub.length);s=sample_meridional(shroud,u*shroud.length)
    h_anchor=[0.];s_anchor=[0.]
    for p,t,h_seed,s_seed in zip(mean,tangent,h,s):
        if flow_path.align_blade_stations_to_crossflow:
            ph,ps=crossflow_pair(hub,shroud,p,t,h_seed,s_seed)
            h_anchor.append(wall_distance(hub,ph)/hub.length)
            s_anchor.append(wall_distance(shroud,ps)/shroud.length)
        else:
            h_anchor.append(wall_distance(hub,h_seed)/hub.length)
            s_anchor.append(wall_distance(shroud,s_seed)/shroud.length)
    h_anchor.append(1.);s_anchor.append(1.)
    if np.any(np.diff(h_anchor)<=0) or np.any(np.diff(s_anchor)<=0):
        raise ValueError("Blade LE/TE cross-flow cuts must increase on both walls.")
    knots=[0.,le,te,1.]
    return np.interp(m_flow_norm,knots,h_anchor),np.interp(m_flow_norm,knots,s_anchor)
