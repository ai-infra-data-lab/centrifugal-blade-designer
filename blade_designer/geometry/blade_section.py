"""Profiles on a surface of revolution. No GUI or external file conventions."""
import numpy as np
from scipy.integrate import cumulative_trapezoid
from ..models.geometry_3d import Curve3D,SectionGeometry3D
from ..models.validation import validate_control_points,ValidationLevel,is_finite_number
from ..models.resolution import GeometryResolutionParameters
from ..models.parameters import EdgeType,SurfaceMapping
from .distributions import interpolate_beta_m_deg
from .thickness import generate_thickness
from .meridional import calculate_meridional
from .edges import generate_edge
from .tangent_arcs import fit_circular_cap, fit_elliptical_cap, contact_intervals
from .checks import has_self_intersection
from .cylindrical_cutoff import cylinder_distance, cut_surface
from .curve_source import resample_source_map



def validate_section(section):
    for kind,points in (("blade_angle",section.blade_angle.points),("thickness",section.thickness.points)):
        errors=[i.message for i in validate_control_points(points,kind) if i.level==ValidationLevel.ERROR]
        if errors: raise ValueError(f"Span {section.span}: {'; '.join(errors)}")
    edge=section.edge_parameters
    if not isinstance(edge.le_type,EdgeType) or not isinstance(edge.te_type,EdgeType):
        raise ValueError("Unknown section edge type.")
    if any(not is_finite_number(v) or v<=0 for v in (edge.le_ellipse_ratio,edge.te_ellipse_ratio)):
        raise ValueError("Section ellipse ratios must be finite and > 0.")


def resample_curve(curve,n_points):
    # Export density never controls the master geometry.
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(curve.xyz,axis=0),axis=1))]
    if arc[-1]==0:
        return Curve3D(*(np.full(n_points,v[0]) for v in (curve.r,curve.theta_rad,curve.z)))
    keep=np.r_[True,np.diff(arc)>1e-14]
    target=np.linspace(0,arc[-1],n_points)
    arrays=[np.interp(target,arc[keep],v[keep]) for v in (curve.r,curve.theta_rad,curve.z)]
    m_blade_norm=None if curve.m_blade_norm is None else np.interp(target,arc[keep],curve.m_blade_norm[keep])
    meridional_distance=None if curve.meridional_distance is None else np.interp(target,arc[keep],curve.meridional_distance[keep])
    source_span=None if curve.source_span is None else np.interp(target,arc[keep],curve.source_span[keep])
    provenance=resample_source_map(curve.source_map,arc,keep,target)
    return Curve3D(*arrays,m_blade_norm,meridional_distance,source_span,provenance)


def generate_section(section,wall_zr,le_fraction,te_fraction,theta_le_rad,counts,mapping,resolution=None,flow_coordinates=None,rotation_sign=1,*,cutoff_radius=None,start_fraction=0.,thickness_scale=1.,theta_te_rad=None,distributions_from_le=False):
    resolution=GeometryResolutionParameters() if resolution is None else resolution
    validate_section(section)
    wall_m,_=calculate_meridional(wall_zr[:,1],wall_zr[:,0])
    # LE/TE reference the same Hub/Shroud flow-path station, even when an
    # intermediate wall has a different arclength parameterization.
    flow_fraction=np.linspace(0,1,len(wall_zr)) if flow_coordinates is None else flow_coordinates
    le_m=float(np.interp(le_fraction,flow_fraction,wall_m))
    te_m=float(np.interp(te_fraction,flow_fraction,wall_m))
    if cutoff_radius is not None:
        te_m=cylinder_distance(wall_m,wall_zr,cutoff_radius,te_m)
    if not np.isfinite([le_m,te_m]).all() or te_m<=le_m:
        raise ValueError(f"Span {section.span}: physical m_TE must exceed m_LE.")
    le_m=le_m+start_fraction*(te_m-le_m)
    m_blade_norm=np.linspace(0,1,resolution.profile_points);m=le_m+(te_m-le_m)*m_blade_norm
    # Independent short blades may define distributions only on their own
    # LE-to-TE interval, while their placement stays on the main-blade axis.
    source_norm=m_blade_norm if distributions_from_le else start_fraction+(1-start_fraction)*m_blade_norm
    def wall_at(distance):
        distance=np.asarray(distance)
        if np.any(distance<-1e-9) or np.any(distance>wall_m[-1]+1e-9):
            raise ValueError("Blade edges/surfaces exceed flow path; extend upstream/downstream or move LE/TE.")
        return np.column_stack([np.interp(distance,wall_m,wall_zr[:,i]) for i in (0,1)])
    zr=wall_at(m);r=zr[:,1]
    if np.any(r<=0): raise ValueError("Blade flow path radius must be > 0.")
    beta_m_deg=interpolate_beta_m_deg(source_norm,section.blade_angle.points)
    beta_m_rad=np.deg2rad(beta_m_deg)
    theta_rad=theta_le_rad+rotation_sign*cumulative_trapezoid(np.tan(beta_m_rad)/r,m,initial=0)
    if theta_te_rad is not None:theta_rad+=theta_te_rad-theta_rad[-1]
    thickness=generate_thickness(source_norm,section.thickness)*thickness_scale
    camber=Curve3D(r,theta_rad,zr[:,0],m_blade_norm,m)
    # Intrinsic normal offset: delta_m=-t*sin(beta)/2, r*delta_theta=t*cos(beta)/2.
    def mapped(distance,theta,tangential,m_blade_norm=None):
        rz=wall_at(distance);radius=rz[:,1]
        if np.any(radius<=0):raise ValueError("Blade surfaces require physical radius R > 0.")
        return Curve3D(radius,theta+rotation_sign*tangential/radius,rz[:,0],m_blade_norm,np.asarray(distance))
    sign=1 if mapping==SurfaceMapping.POSITIVE_IS_PS else -1 if mapping==SurfaceMapping.NEGATIVE_IS_PS else (-1 if np.mean(beta_m_deg)>0 else 1)
    dm=-thickness*np.sin(beta_m_rad)/2;dy=thickness*np.cos(beta_m_rad)/2
    def surface(side):
        distance=m+side*dm
        if cutoff_radius is None:
            return mapped(distance,theta_rad,side*dy,m_blade_norm)
        coordinates=cut_surface(distance,theta_rad,side*dy,m_blade_norm,te_m,
                                side*dm[-1],beta_m_rad[-1],wall_m,wall_zr[:,1],rotation_sign,te_m-le_m)
        curve=mapped(*coordinates)
        curve.r[-1]=cutoff_radius
        return curve
    ps=surface(sign)
    ss=surface(-sign)
    # Single-circle rounding moves contacts along the original side curves.
    # The m/theta splines are shared by root evaluation and trimmed-side output.
    caps={};kinds=(section.edge_parameters.le_type,section.edge_parameters.te_type)
    if any(kind!=EdgeType.CUTOFF for kind in kinds):
        from scipy.interpolate import make_interp_spline
        originals=(ps,ss)
        coordinates=[np.linspace(0,1,len(c.r)) for c in originals]
        splines=[make_interp_spline(u,np.column_stack((c.meridional_distance,c.theta_rad)),k=3) for u,c in zip(coordinates,originals)]
        derivatives=[s.derivative() for s in splines]
        class LocalSide:
            def __init__(self,spline,derivative,theta_reference):
                self.spline=spline;self.slope=derivative;self.reference=theta_reference
            def evaluate(self,q):
                distance,theta=self.spline(q).T;radius=wall_at(np.atleast_1d(distance))[0,1]
                return np.array([distance,rotation_sign*(theta-self.reference)*radius])
            def derivative(self,q):
                distance,theta=self.spline(q);dm,dtheta=self.slope(q)
                radius=wall_at(np.array([distance]))[0,1]
                k=int(np.clip(np.searchsorted(wall_m,distance,side='right')-1,0,len(wall_m)-2))
                dr=(wall_zr[k+1,1]-wall_zr[k,1])/(wall_m[k+1]-wall_m[k])
                return np.array([dm,rotation_sign*(dtheta*radius+(theta-self.reference)*dr*dm)])
        for leading,kind,index in ((True,kinds[0],0),(False,kinds[1],-1)):
            if kind!=EdgeType.CUTOFF:
                sides=[LocalSide(s,d,theta_rad[index]) for s,d in zip(splines,derivatives)]
                direction=np.array([np.cos(beta_m_rad[index]),np.sin(beta_m_rad[index])])
                ratio=section.edge_parameters.le_ellipse_ratio if leading else section.edge_parameters.te_ellipse_ratio
                caps[leading]=(fit_elliptical_cap(*sides,leading,direction,ratio)
                               if kind==EdgeType.ELLIPTICAL else fit_circular_cap(*sides,leading,direction))
        trimmed=[]
        for spline,source,u,interval in zip(splines,originals,coordinates,contact_intervals(caps)):
            q=np.linspace(*interval,len(source.r));distance,theta=spline(q).T
            norm=np.interp(q,u,source.m_blade_norm)
            curve=mapped(distance,theta,np.zeros(len(q)),norm)
            if cutoff_radius is not None:curve.r[-1]=cutoff_radius
            trimmed.append(curve)
        ps,ss=trimmed
    edges=[]
    for index,leading,kind,ratio in ((0,True,kinds[0],section.edge_parameters.le_ellipse_ratio),
                                   (-1,False,kinds[1],section.edge_parameters.te_ellipse_ratio)):
        beta=beta_m_rad[index];center=np.array([m[index],0.])
        if leading in caps:
            xy=caps[leading].sample(resolution.edge_points)
            edges.append(mapped(xy[:,0],np.full(len(xy),theta_rad[index]),xy[:,1]))
            continue
        if not leading and cutoff_radius is not None:
            n=resolution.edge_points
            edges.append(Curve3D(np.full(n,cutoff_radius),
                np.linspace(ps.theta_rad[-1],ss.theta_rad[-1],n),
                np.full(n,ps.z[-1]),meridional_distance=np.full(n,te_m)))
            continue
        plus=np.array([sign*dm[index],sign*dy[index]])
        edge=generate_edge(center,np.array([np.cos(beta),np.sin(beta)]),center+plus,center-plus,kind,ratio,leading,resolution.edge_points)
        edges.append(mapped(edge.x,np.full(len(edge.x),theta_rad[index]),edge.y))
    le,te=edges
    # Set exact common endpoints to eliminate trigonometric rounding at joins.
    for edge,first,last in ((le,ss,ps),(te,ps,ss)):
        index=0 if edge is le else -1
        for name in ("r","theta_rad","z"):
            getattr(edge,name)[0]=getattr(first,name)[index];getattr(edge,name)[-1]=getattr(last,name)[index]
    for curve in (camber,ps,ss,le,te):
        if not np.all(np.isfinite(curve.xyz)): raise ValueError("Non-finite blade coordinates.")
        if cutoff_radius is not None and np.any(curve.r > cutoff_radius+1e-9):
            raise ValueError("TE Cutoff: blade profile extends outside the Hub TE cylinder.")
    # On a nonintersecting wall, (meridional distance, unwrapped theta) is
    # a chart of the surface. Validate the master contour before resampling.
    chart=np.concatenate([np.column_stack((curve.meridional_distance,curve.theta_rad*np.mean(r)))[sl]
                          for curve,sl in ((le,slice(None,-1)),(ps,slice(None,-1)),
                              (te,slice(None,-1)),(ss,slice(None,0,-1)))])
    chart=chart[np.r_[True,np.linalg.norm(np.diff(chart,axis=0),axis=1)>1e-12]]
    if np.linalg.norm(chart[-1]-chart[0])<1e-12:chart=chart[:-1]
    if has_self_intersection(chart):raise ValueError(f"Span {section.span}: blade profile self intersection or zero interior thickness.")
    if np.any(np.abs(dy/r)>=np.pi):raise ValueError("Thickness wraps the profile around the rotation axis.")
    return SectionGeometry3D(section.span,camber,resample_curve(ps,counts.ps_points),resample_curve(ss,counts.ss_points),
        resample_curve(le,counts.le_points),resample_curve(te,counts.te_points),ps,ss,le,te,m,beta_m_deg,thickness)
