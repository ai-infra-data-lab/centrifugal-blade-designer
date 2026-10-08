"""Exact wall projection and span correspondence, without GUI dependencies."""
import numpy as np
from ..models.meridional import ArcSegmentGeometry,LineSegmentGeometry,Point2D
from .meridional_segments import sample_meridional,intersections

def edge_endpoints(edge,hub,shroud):
    return np.array([sample_meridional(hub,np.array([edge.hub_m_flow_norm*hub.length]))[0],
                     sample_meridional(shroud,np.array([edge.shroud_m_flow_norm*shroud.length]))[0]])

def interpolate_edge_position(edge,hub,shroud,span):
    if not np.isfinite(span) or not 0<=span<=1:raise ValueError("Span must be finite within [0,1].")
    a,b=edge_endpoints(edge,hub,shroud)
    return (1-span)*a+span*b

def validate_blade_edges(edges,hub=None,shroud=None):
    values=np.array([[e.hub_m_flow_norm,e.shroud_m_flow_norm] for e in (edges.leading_edge,edges.trailing_edge)])
    if not np.isfinite(values).all() or np.any(values<0) or np.any(values>1):
        raise ValueError("Blade edge positions must be finite within [0,1].")
    if np.any(values[1]<=values[0]):raise ValueError("Blade edges require TE > LE on Hub, Shroud and every span.")
    refs=[edges.reference_le_fraction,edges.reference_te_fraction]
    if not np.isfinite(refs).all() or not 0<=refs[0]<refs[1]<=1:
        raise ValueError("Blade correspondence knots require 0 <= LE < TE <= 1.")
    if not isinstance(edges.legacy_uniform_sampling,bool):raise ValueError("Invalid blade sampling flag.")
    if hub is not None:
        lines=[]
        for edge in (edges.leading_edge,edges.trailing_edge):
            a,b=edge_endpoints(edge,hub,shroud);length=float(np.linalg.norm(b-a))
            lines.append(LineSegmentGeometry(Point2D(*a),Point2D(*b),(b-a)/length,(b-a)/length,length))
        if intersections(*lines):raise ValueError("Blade LE/TE lines cross or touch.")

def blade_wall_parameters(edges,coordinates):
    refs=[0.,edges.reference_le_fraction,edges.reference_te_fraction,1.]
    # Endpoint knots may coincide with full wall ends; the blade itself still
    # validates cap extent against the finite flow path.
    if edges.reference_le_fraction==0 or edges.reference_te_fraction==1:
        for wall in ("hub","shroud"):
            vals=[getattr(e,wall+"_m_flow_norm") for e in (edges.leading_edge,edges.trailing_edge)]
            if (refs[1]==0 and vals[0]!=0) or (refs[2]==1 and vals[1]!=1):
                raise ValueError("Wall-end correspondence knots must match wall endpoints.")
    return tuple(np.interp(coordinates,refs,[0,getattr(edges.leading_edge,w+"_m_flow_norm"),
                        getattr(edges.trailing_edge,w+"_m_flow_norm"),1]) for w in ("hub","shroud"))

def project_to_wall(wall,zr):
    """Nearest analytic Line/Arc point, returning normalized physical distance."""
    point=np.asarray(zr,dtype=float)
    if point.shape!=(2,) or not np.isfinite(point).all():raise ValueError("Projection point must be finite Z,R.")
    candidates=[];offset=0.
    for segment in wall.segments:
        if isinstance(segment,ArcSegmentGeometry):
            v=point-segment.center.zr;a=segment.start.zr-segment.center.zr
            angle=np.arctan2(a[0]*v[1]-a[1]*v[0],a@v)
            angle=((-angle) if segment.clockwise else angle)%(2*np.pi)
            distances=[0.,segment.length]
            if angle<=abs(segment.sweep_rad)+1e-12 and np.linalg.norm(v)>0:
                distances.append(min(angle*segment.radius,segment.length))
        else:distances=[float(np.clip((point-segment.start.zr)@segment.start_tangent,0,segment.length))]
        for distance in distances:
            m=offset+distance;candidate=sample_meridional(wall,np.array([m]))[0]
            candidates.append((float(np.linalg.norm(candidate-point)),m,candidate))
        offset+=segment.length
    _,m,candidate=min(candidates,key=lambda v:v[0])
    return float(m/wall.length),candidate
