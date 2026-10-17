"""Gross passage area from actual wall intersections with the mean-line normal.

No blade blockage, effective area or matched-index width approximation is used.
Coordinates and areas use the engine's mm and mm² units.
"""
import numpy as np
from ..models.flow_area import FlowAreaStation,FlowAreaResult
from ..models.flow_path import FlowPathParameters
from ..models.meridional import ArcSegmentGeometry
from .meridional_segments import _contains, sample_meridional,validate_flow_path
from .flow_path import sample_mean_line,region_at,validate_component_stations

def crossflow_intersections(wall,mean,tangent):
    """Intersect an infinite normal line with exact finite Line/Arc primitives."""
    normal=np.array([-tangent[1],tangent[0]])
    if hasattr(wall,'source_m'):
        points=np.column_stack((wall.z,wall.r));a=points[:-1];delta=np.diff(points,axis=0)
        denom=delta@tangent
        f=np.divide((mean-a)@tangent,denom,out=np.full(len(a),-1.),where=np.abs(denom)>1e-12)
        hits=a[(f>=-1e-9)&(f<=1+1e-9)]+delta[(f>=-1e-9)&(f<=1+1e-9)]*f[(f>=-1e-9)&(f<=1+1e-9),None]
        result=[]
        for hit in hits:
            if not any(np.linalg.norm(hit-p)<1e-7 for p in result):result.append(hit)
        return result
    hits=[]
    for segment in wall.segments:
        if isinstance(segment,ArcSegmentGeometry):
            projection=float((segment.center.zr-mean)@tangent)
            discriminant=segment.radius**2-projection**2
            if discriminant < -1e-9:continue
            base=segment.center.zr-projection*tangent
            root=np.sqrt(max(0.,discriminant))
            candidates=(base+root*normal,base-root*normal)
        else:
            denominator=float(segment.start_tangent@tangent)
            if abs(denominator)<1e-12:continue
            distance=float((mean-segment.start.zr)@tangent)/denominator
            candidates=(segment.start.zr+distance*segment.start_tangent,)
        for point in candidates:
            if _contains(segment,point) and not any(np.linalg.norm(point-p)<1e-7 for p in hits):
                hits.append(point)
    return hits

def crossflow_pair(hub,shroud,mean,tangent,expected_hub,expected_shroud):
    h=crossflow_intersections(hub,mean,tangent)
    s=crossflow_intersections(shroud,mean,tangent)
    if not h or not s:
        raise ValueError("Cross-flow normal does not intersect both finite walls; align or extend inlet/outlet geometry.")
    normal=np.array([-tangent[1],tangent[0]])
    pairs=[(ph,ps) for ph in h for ps in s
           if float((ph-mean)@normal)*float((ps-mean)@normal)<=1e-8]
    if not pairs:raise ValueError("Cross-flow wall intersections do not bracket the mean line.")
    # Select the local branch nearest the corresponding arc-fraction seed on each
    # wall. Remote intersections in folded passages must not replace local walls.
    ranked=sorted(pairs,key=lambda pair:np.linalg.norm(pair[0]-expected_hub)+np.linalg.norm(pair[1]-expected_shroud))
    if len(ranked)>1:
        costs=[np.linalg.norm(a-expected_hub)+np.linalg.norm(b-expected_shroud) for a,b in ranked[:2]]
        if abs(costs[1]-costs[0])<1e-7:raise ValueError("Ambiguous cross-flow intersections in a folded passage.")
    return ranked[0]

def calculate_flow_area(hub,shroud,parameters=None,points=501,strict=True,mean_points=4001):
    parameters=FlowPathParameters() if parameters is None else parameters
    named_positions=validate_component_stations(parameters)
    validate_flow_path(hub,shroud)
    if not isinstance(points,int) or isinstance(points,bool) or points<3:
        raise ValueError("Flow-area sampling requires an integer >= 3.")
    positions=np.unique(np.r_[np.linspace(0,1,points),named_positions])
    u,mean,tangents,total=sample_mean_line(hub,shroud,positions,mean_points)
    expected_h=sample_meridional(hub,u*hub.length)
    expected_s=sample_meridional(shroud,u*shroud.length)
    stations=[];by_position={};errors=[]
    for position,p,t,h_seed,s_seed in zip(positions,mean,tangents,expected_h,expected_s):
        try:
            h,s=crossflow_pair(hub,shroud,p,t,h_seed,s_seed)
            length=float(np.linalg.norm(s-h))
            area=float(np.pi*(h[1]+s[1])*length)
            if not np.isfinite([length,area,*h,*s]).all() or length<=0 or area<=0 or min(h[1],s[1])<=0:
                raise ValueError("Non-positive or non-finite cross-flow passage area.")
            station=FlowAreaStation(float(position),float(position*total),*map(float,p),
                                    *map(float,h),*map(float,s),length,area,region_at(parameters,float(position)))
            stations.append(station);by_position[float(position)]=station
        except ValueError as exc:
            message=f"m_flow_norm={position:.8g}: {exc}"
            if strict:raise ValueError(message) from exc
            errors.append(message)
    named={station.kind.value:by_position.get(float(station.m_flow_norm)) for station in parameters.stations}
    return FlowAreaResult(stations,named,errors)
