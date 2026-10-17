"""Analytic G1 chains in (Z,R); positive angle rotates +Z toward +R."""
import numpy as np
from ..models.meridional import (Point2D, LineSegmentParameters, ArcSegmentParameters,
    MeridionalCurveParameters, LineSegmentGeometry, ArcSegmentGeometry, MeridionalGeometry)


def _rotate(vector, angle):
    c,s = np.cos(angle),np.sin(angle)
    return np.array([[c,-s],[s,c]]) @ vector


def convert_segment_type(segment,arc):
    """Change primitive type, retaining physical length and row ownership."""
    length=(segment.radius*abs(np.deg2rad(segment.sweep_deg))
            if isinstance(segment,ArcSegmentParameters) else segment.length)
    if not np.isfinite(length) or length<=0:
        raise ValueError("Segment conversion requires a positive finite length.")
    if arc:
        result=ArcSegmentParameters(blade_row=segment.blade_row)
        result.radius=float(length/np.deg2rad(result.sweep_deg))
        return result
    return LineSegmentParameters(length=float(length),blade_row=segment.blade_row)


def evaluate_segment(segment, distance):
    distance = np.asarray(distance,dtype=np.float64)
    if isinstance(segment,ArcSegmentGeometry):
        angle = (-1 if segment.clockwise else 1)*distance/segment.radius
        v = segment.start.zr-segment.center.zr
        return segment.center.zr + np.stack((v[0]*np.cos(angle)-v[1]*np.sin(angle),
                                            v[0]*np.sin(angle)+v[1]*np.cos(angle)),axis=-1)
    return segment.start.zr + distance[...,None]*segment.start_tangent


def sample_meridional(geometry, distance):
    distance = np.asarray(distance,dtype=np.float64)
    if np.any(~np.isfinite(distance)) or np.any(distance < -1e-9) or np.any(distance > geometry.length+1e-9):
        raise ValueError("Profile exceeds the meridional flow path; extend upstream/downstream segments.")
    if hasattr(geometry,'source_m'):
        return np.stack((np.interp(distance,geometry.m,geometry.z),np.interp(distance,geometry.m,geometry.r)),axis=-1)
    boundaries = np.r_[0,np.cumsum([s.length for s in geometry.segments])]
    index = np.clip(np.searchsorted(boundaries,distance,side="right")-1,0,len(geometry.segments)-1)
    result = np.empty(distance.shape+(2,))
    for i,seg in enumerate(geometry.segments):
        mask = index == i
        result[mask] = evaluate_segment(seg,np.clip(distance[mask]-boundaries[i],0,seg.length))
    return result


def _contains(segment, p, tol=1e-8):
    if isinstance(segment,ArcSegmentGeometry):
        v0 = segment.start.zr-segment.center.zr
        v = p-segment.center.zr
        if abs(np.linalg.norm(v)-segment.radius)>tol: return False
        a = np.arctan2(v[1],v[0])-np.arctan2(v0[1],v0[0])
        delta = ((-a if segment.clockwise else a) % (2*np.pi))
        return delta <= abs(segment.sweep_rad)+tol or np.linalg.norm(p-segment.start.zr)<tol
    d = p-segment.start.zr
    return abs((segment.start_tangent[0]*d[1]-segment.start_tangent[1]*d[0]))<tol and -tol <= d@segment.start_tangent <= segment.length+tol


def intersections(a,b):
    """Exact primitive intersections, including tangency and coincident overlap."""
    aa,bb = isinstance(a,ArcSegmentGeometry),isinstance(b,ArcSegmentGeometry)
    if not aa and bb: return intersections(b,a)
    candidates=[]
    if not aa:
        p,q=a.start.zr,b.start.zr
        u,v=a.end.zr-p,b.end.zr-q
        cross=lambda x,y: float(x[0]*y[1]-x[1]*y[0])
        det=cross(u,v)
        if abs(det)>1e-12:
            candidates=[p+u*cross(q-p,v)/det]
        elif abs(cross(q-p,u))<1e-8:
            candidates=[a.start.zr,a.end.zr,b.start.zr,b.end.zr]
    elif not bb:
        d=b.start.zr-a.center.zr; t=b.start_tangent
        roots=np.roots([1,2*d@t,d@d-a.radius**2])
        candidates=[b.start.zr+float(x.real)*t for x in roots if abs(x.imag)<1e-8]
    else:
        dvec=b.center.zr-a.center.zr; d=np.linalg.norm(dvec)
        if d<1e-10:
            if abs(a.radius-b.radius)<1e-8:
                candidates=[a.start.zr,a.end.zr,b.start.zr,b.end.zr,
                            evaluate_segment(a,a.length/2),evaluate_segment(b,b.length/2)]
        elif abs(a.radius-b.radius)-1e-8 <= d <= a.radius+b.radius+1e-8:
            x=(a.radius**2-b.radius**2+d*d)/(2*d)
            h=np.sqrt(max(0,a.radius**2-x*x)); u=dvec/d
            mid=a.center.zr+x*u; n=np.array([-u[1],u[0]])
            candidates=[mid+h*n,mid-h*n]
    return [p for p in candidates if _contains(a,p) and _contains(b,p)]


def generate_meridional(params: MeridionalCurveParameters, points_per_segment=201) -> MeridionalGeometry:
    if not np.all(np.isfinite([params.start_z,params.start_r,params.start_angle_deg])):
        raise ValueError("Meridional start conditions must be finite.")
    if params.start_r<=0 or not params.segments:
        raise ValueError("Meridional curve requires positive R and at least one segment.")
    if not isinstance(params.export_points,int) or isinstance(params.export_points,bool) or params.export_points<2:
        raise ValueError("Meridional export point count must be an integer >= 2.")
    p=Point2D(params.start_z,params.start_r)
    angle=np.deg2rad(params.start_angle_deg); t=np.array([np.cos(angle),np.sin(angle)])
    segments=[]; samples=[]; distances=[]; total=0.
    for definition in params.segments:
        if isinstance(definition,ArcSegmentParameters):
            r,sweep=definition.radius,definition.sweep_deg
            if not np.all(np.isfinite([r,sweep])) or r<=0 or not 0<sweep<360 or not isinstance(definition.clockwise,bool):
                raise ValueError("Arc requires finite radius > 0 and 0 < sweep < 360 degrees, CW/CCW boolean.")
            sign=-1 if definition.clockwise else 1
            center=Point2D(*(p.zr+sign*r*np.array([-t[1],t[0]])))
            turn=sign*np.deg2rad(sweep); end=Point2D(*(center.zr+_rotate(p.zr-center.zr,turn)))
            seg=ArcSegmentGeometry(p,end,t.copy(),_rotate(t,turn),r*abs(turn),center,r,turn,definition.clockwise)
            # Include radial extrema in validation, independent of preview resolution.
            for candidate in (center.zr+np.array([0,r]),center.zr-np.array([0,r])):
                if _contains(seg,candidate) and candidate[1]<=1e-10:
                    raise ValueError("Arc crosses negative physical radius R.")
        elif isinstance(definition,LineSegmentParameters):
            length=definition.length
            if not np.isfinite(length) or length<=0: raise ValueError("Line length must be finite and > 0.")
            end=Point2D(*(p.zr+length*t)); seg=LineSegmentGeometry(p,end,t.copy(),t.copy(),length)
        else: raise ValueError("Unknown meridional segment type.")
        if seg.end.r <= 1e-10: raise ValueError("Meridional curve crosses negative physical radius R.")
        for i,previous in enumerate(segments):
            hits=intersections(previous,seg)
            if any(i != len(segments)-1 or np.linalg.norm(hit-p.zr)>1e-7 for hit in hits):
                raise ValueError("Meridional curve self intersection.")
        segments.append(seg)
        local=np.linspace(0,seg.length,points_per_segment)
        if len(segments)>1: local=local[1:]
        samples.append(evaluate_segment(seg,local))
        distances.append(total + local)
        total+=seg.length;p=seg.end;t=seg.end_tangent.copy()
    zr=np.concatenate(samples)
    if not np.all(np.isfinite(zr)): raise ValueError("Non-finite meridional geometry.")
    # Exact primitive arc length, independent of display sampling density.
    m=np.concatenate(distances)
    return MeridionalGeometry(segments,zr[:,0],zr[:,1],m)


def validate_flow_path(hub,shroud):
    if any(intersections(a,b) for a in hub.segments for b in shroud.segments):
        raise ValueError("Hub/Shroud intersection or contact.")
