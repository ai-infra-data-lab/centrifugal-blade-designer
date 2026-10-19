"""Cut a generated blade surface without modifying its design distributions.

Units: mm, rad, mm². Span surfaces use piecewise cylindrical interpolation
between the generated source sections; all clipping retains source coordinates.
"""
from copy import deepcopy
from dataclasses import dataclass
import numpy as np
from scipy.spatial import cKDTree
from ..models.validation import validate_impeller_trim as validate_trim
from ..models.geometry_3d import Curve3D, ImpellerGeometry, TipMeridionalGeometry
from ..models.meridional import MeridionalGeometry, Point2D, LineSegmentGeometry
from .meridional_segments import sample_meridional, validate_flow_path
from .flow_path import sample_mean_line
from .flow_area import crossflow_pair
from .blade_section import resample_curve
from .surface_evaluation import interpolate_span_columns as _blend
from .curve_source import source_map, blend_source_map, ROLES


def trim_active(settings):
    validate_trim(settings)
    return settings is not None and (settings.shroud_area_cut_percent>0 or
        settings.diameter_mode=='diameter' or
        settings.diameter_mode=='percent' and settings.diameter_cut_percent>0)


def area_fraction(hub_r,shroud_r,width,retained):
    """Stable positive root of pi*b*t*(2*Rh+t*(Rs-Rh))=retained*A0."""
    h,s,b=np.broadcast_arrays(hub_r,shroud_r,width)
    if not 0<retained<=1 or np.any(h<=0) or np.any(s<=0) or np.any(b<=0):
        raise ValueError('Invalid reference area or retained fraction.')
    k=retained*(h+s)
    return 2*k/(2*h+np.sqrt(4*h*h+4*(s-h)*k))


@dataclass
class DerivedWall(MeridionalGeometry):
    source_m: np.ndarray
    source_boundaries: np.ndarray


def _wall(points,source_m,source_boundaries):
    delta=np.diff(points,axis=0);length=np.linalg.norm(delta,axis=1)
    if np.any(length<1e-10) or np.any(points[:,1]<=0) or not np.isfinite(points).all():
        raise ValueError('Impeller trim creates a degenerate casing.')
    m=np.r_[0,np.cumsum(length)]
    segments=[LineSegmentGeometry(Point2D(*a),Point2D(*b),t,t,float(d))
              for a,b,t,d in zip(points[:-1],points[1:],delta/length[:,None],length)]
    return DerivedWall(segments,points[:,0],points[:,1],m,source_m,source_boundaries)


def _casing(base,cut):
    # Fixed ORIGINAL mean-normal planes, including original wall joins.
    joins=np.r_[np.cumsum([s.length for s in base.shroud.segments])/base.shroud.length,
                np.cumsum([s.length for s in base.hub.segments])/base.hub.length]
    positions=np.unique(np.r_[np.linspace(0,1,1001),joins])
    positions=positions[np.r_[True,np.diff(positions)>1e-12]];positions[-1]=1.
    u,mean,tangents,_=sample_mean_line(base.hub,base.shroud,positions)
    hs=sample_meridional(base.hub,u*base.hub.length)
    ss=sample_meridional(base.shroud,u*base.shroud.length)
    points=[];reference=[];original=[]
    for p,t,h,s in zip(mean,tangents,hs,ss):
        h,s=crossflow_pair(base.hub,base.shroud,p,t,h,s)
        width=np.linalg.norm(s-h)
        f=float(area_fraction(h[1],s[1],width,1-cut/100))
        points.append(h+f*(s-h));reference.append((h[1],s[1],width,f));original.append(s)
    points=np.asarray(points)
    # Source arclength is attached via the actual original casing intersection.
    from .blade_edge import project_to_wall
    source=np.array([project_to_wall(base.shroud,s)[0]*base.shroud.length
                     for s in original])
    if np.any(np.diff(source)<=0):raise ValueError('Impeller trim casing reference reverses direction.')
    boundaries=np.r_[0,np.cumsum([s.length for s in base.shroud.segments])]
    wall=_wall(points,source,boundaries)
    validate_flow_path(base.hub,wall)
    # Nonlocal segment crossings must not produce a folded derived wall.
    _check_polyline(points)
    return wall,np.asarray(reference)


def _restore_downstream(base,result):
    """Restore the original casing beyond the complete retained Tip profile.

    A quintic blend has zero first/second derivative at both ends. Keep the
    cutting boundary separate: changing the outlet must not regenerate blades.
    """
    wall=result.shroud
    points=np.column_stack((wall.z,wall.r))
    tree=cKDTree(points)
    def wall_distances(zr):
        _,nearest=tree.query(zr)
        indices=np.clip(np.column_stack((nearest-1,nearest)),0,len(points)-2)
        starts=points[indices];delta=points[indices+1]-starts
        fraction=np.clip(np.sum((zr[:,None,:]-starts)*delta,axis=2)/np.sum(delta*delta,axis=2),0,1)
        error=np.linalg.norm(starts+fraction[:,:,None]*delta-zr[:,None,:],axis=2)
        choose=np.argmin(error,axis=1);rows=np.arange(len(zr))
        index=indices[rows,choose]
        return wall.m[index]+fraction[rows,choose]*(wall.m[index+1]-wall.m[index])
    distances=[]
    for group in (result.sections,result.splitter_sections or []):
        if not group:continue
        s=group[-1]
        for name in ('camber','master_le','master_ps','master_te','master_ss'):
            curve=getattr(s,name)
            distances.extend(wall_distances(np.column_stack((curve.z,curve.r))))
    start=float(np.interp(max(distances),wall.m,wall.source_m))
    end=float(wall.source_m[-1])
    if end-start<=max(1e-8,end*1e-9):
        raise ValueError('Shroud restoration requires a downstream interval beyond the complete blade TE.')
    source=np.sort(np.r_[wall.source_m[np.abs(wall.source_m-start)>1e-10],start])
    old_m=np.interp(source,wall.source_m,wall.m)
    cut=sample_meridional(wall,old_m)
    original=sample_meridional(base.shroud,source)
    t=np.clip((source-start)/(end-start),0,1)
    weight=t**3*(10-15*t+6*t*t)
    restored=cut+weight[:,None]*(original-cut)
    if np.any(np.einsum('ij,ij->i',np.diff(restored,axis=0),np.diff(cut,axis=0))<=0):
        raise ValueError('Shroud restoration folds or reverses along the original passage.')
    new_wall=_wall(restored,source,wall.source_boundaries)
    validate_flow_path(base.hub,new_wall);_check_polyline(restored)
    # Carry the generated Tip's distance correspondence through the new wall.
    tip=result.tip
    tip_points=np.column_stack((np.interp(old_m,tip.casing_m,tip.z),
                                np.interp(old_m,tip.casing_m,tip.r)))+restored-cut
    _check_polyline(tip_points)
    result.tip=TipMeridionalGeometry(new_wall.m,tip_points[:,0],tip_points[:,1],
        np.interp(old_m,tip.casing_m,tip.clearance_mm),
        float(np.interp(tip.le_casing_m,old_m,new_wall.m)),
        float(np.interp(tip.te_casing_m,old_m,new_wall.m)))
    result.shroud=new_wall


def _check_polyline(points):
    # All nonadjacent segment pairs; vectorized O(N²), bounded by wall resolution.
    a=points[:-1];v=np.diff(points,axis=0)
    for i in range(len(a)-2):
        w=v[i+2:];d=a[i+2:]-a[i]
        det=v[i,0]*w[:,1]-v[i,1]*w[:,0]
        good=np.abs(det)>1e-12
        t=np.divide(d[:,0]*w[:,1]-d[:,1]*w[:,0],det,out=np.full(len(w),-1.),where=good)
        q=np.divide(d[:,0]*v[i,1]-d[:,1]*v[i,0],det,out=np.full(len(w),-1.),where=good)
        if np.any(good & (t>=0)&(t<=1)&(q>=0)&(q<=1)):
            raise ValueError('Impeller trim creates a self-intersecting boundary.')


class _Boundary:
    def __init__(self,points,hub):
        self.points=points;self.tree=cKDTree(points)
        v=np.gradient(points,axis=0);v/=np.linalg.norm(v,axis=1)[:,None]
        self.normals=np.column_stack((-v[:,1],v[:,0]))
        h=sample_meridional(hub,np.linspace(0,hub.length,len(points)))
        signs=np.einsum('ij,ij->i',h-points,self.normals)
        if np.any(np.abs(signs)<1e-8) or np.any(signs*signs[0]<=0):
            raise ValueError('Impeller trim has ambiguous Hub-side normals.')
        self.normals*=np.sign(signs[0])

    def signed(self,points):
        # Nearest finite polyline segment; do not snap the generated surface.
        _,nearest=self.tree.query(points)
        indices=np.stack((np.maximum(nearest-1,0),np.minimum(nearest,len(self.points)-2)),axis=1)
        a=self.points[indices];v=self.points[indices+1]-a
        q=points[:,None,:]-a
        fraction=np.clip(np.sum(q*v,axis=2)/np.sum(v*v,axis=2),0,1)
        projection=a+fraction[:,:,None]*v
        residual=points[:,None,:]-projection
        choice=np.argmin(np.sum(residual**2,axis=2),axis=1)
        index=indices[np.arange(len(points)),choice]
        normal=self.normals[index]
        return np.einsum('ij,ij->i',residual[np.arange(len(points)),choice],normal)


def _span_curve(sections,name,boundary,fraction,source_set='sections'):
    curves=[getattr(s,name) for s in sections]
    if fraction==0:
        result=deepcopy(curves[0])
        result.source_map=source_map(0.,len(result.r),name,source_set)
        return result
    spans=np.array([s.span for s in sections]);n=max(len(c.r) for c in curves)
    values={key:np.array([np.interp(np.linspace(0,1,n),np.linspace(0,1,len(c.r)),getattr(c,key)) for c in curves])
            for key in ('r','theta_rad','z','m_blade_norm','meridional_distance') if getattr(curves[0],key) is not None}
    zr=np.stack((values['z'],values['r']),axis=2)
    signed=np.array([boundary.signed(p) for p in zr])
    if np.any(signed[0]<-1e-7) or np.any(signed[-1]>1e-6):
        raise ValueError('Impeller trim boundary is outside the source blade surface.')
    if np.any(np.diff(signed,axis=0)>1e-6):
        raise ValueError('Impeller trim has missing or multiple span intersections.')
    lo=np.zeros(n);hi=np.ones(n)
    for _ in range(42):
        mid=(lo+hi)/2
        points=np.column_stack((_blend(values['z'],spans,mid),_blend(values['r'],spans,mid)))
        inside=boundary.signed(points)>=0
        lo=np.where(inside,mid,lo);hi=np.where(inside,hi,mid)
    target=(lo+hi)/2*fraction
    provenance=source_map(0.,n,name,source_set,'trim_common_index')
    provenance.coordinates[:,0,0]=target
    return Curve3D(**{key:_blend(v,spans,target) for key,v in values.items()},source_span=target,source_map=provenance)


def _crop_curve(curve,radius):
    r=curve.r
    if r[0]>=radius-1e-9:raise ValueError('Impeller diameter cut reaches the LE or removes the splitter.')
    hits=np.flatnonzero((r[:-1]<radius)&(r[1:]>=radius))
    if len(hits)!=1 or np.any(r[hits[0]+1:]<radius-1e-8):
        raise ValueError('Impeller diameter cut requires one outward crossing on every side.')
    i=int(hits[0]);f=(radius-r[i])/(r[i+1]-r[i])
    result={}
    for key in ('r','theta_rad','z','m_blade_norm','meridional_distance','source_span'):
        v=getattr(curve,key)
        result[key]=None if v is None else np.r_[v[:i+1],v[i]+f*(v[i+1]-v[i])]
    result['r'][-1]=radius
    result['source_map']=blend_source_map(curve.source_map,
        np.r_[np.arange(i+1),i],np.r_[np.arange(i+1),i+1],np.r_[np.zeros(i+1),f])
    return Curve3D(**result)


def _diameter_section(section,radius):
    if np.max(section.master_le.r)>=radius-1e-9:
        raise ValueError('Impeller diameter cut reaches the leading-edge cap.')
    for name in ('camber','master_ps','master_ss'):
        setattr(section,name,_crop_curve(getattr(section,name),radius))
    ps,ss=section.master_ps,section.master_ss
    # Flat machined TE on the cylindrical cut, ordered PS -> SS.
    f=np.linspace(0,1,len(section.master_te.r))
    section.master_te=Curve3D(**{key:(None if getattr(ps,key) is None else getattr(ps,key)[-1]*(1-f)+getattr(ss,key)[-1]*f)
        for key in ('r','theta_rad','z','m_blade_norm','meridional_distance','source_span')})
    for name in ('ps','ss','te'):
        setattr(section,name,resample_curve(getattr(section,'master_'+name),len(getattr(section,name).r)))


def apply_trim(base,params):
    settings=params.impeller_trim
    if not trim_active(settings):return base
    result=deepcopy(base);result.source_geometry=base
    for source_set in ('sections','splitter_sections'):
        for section in getattr(result,source_set) or []:
            for role in ROLES:
                curve=getattr(section,role)
                curve.source_map=source_map(section.span,len(curve.r),role,source_set)
    base_diameter=2*float(base.sections[0].camber.r[-1])
    diameter=(settings.diameter_mm if settings.diameter_mode=='diameter' else
              base_diameter*(1-settings.diameter_cut_percent/100))
    od=settings.diameter_mode!='off' and diameter<base_diameter-1e-9
    if settings.diameter_mode=='diameter' and diameter>base_diameter+1e-9:
        raise ValueError('Impeller trim diameter exceeds the original Hub TE diameter.')
    if settings.shroud_area_cut_percent:
        casing,reference=_casing(base,settings.shroud_area_cut_percent)
        points=np.column_stack((casing.z,casing.r))
        boundary=_Boundary(points,base.hub)
        gap=params.tip_clearance
        clear=np.zeros(len(points))
        le=base.tip.le_casing_m if base.tip is not None else params.impeller_edges.leading_edge.shroud_m_flow_norm*base.shroud.length
        te=base.tip.te_casing_m if base.tip is not None else params.impeller_edges.trailing_edge.shroud_m_flow_norm*base.shroud.length
        new_le,new_te=np.interp([le,te],casing.source_m,casing.m)
        if gap is not None:
            clear=np.interp(casing.m,[new_le,new_te],[gap.le_mm,gap.te_mm])
            points=points+boundary.normals*clear[:,None]
            _check_polyline(points)
            boundary=_Boundary(points,base.hub)
        result.shroud=casing
        result.tip=TipMeridionalGeometry(casing.m,points[:,0],points[:,1],clear,
            float(new_le),float(new_te))
        for attr in ('sections','splitter_sections'):
            source=getattr(base,attr)
            if not source:continue
            target=getattr(result,attr)
            for s in target:
                for name in ('camber','master_ps','master_ss','master_le','master_te'):
                    setattr(s,name,_span_curve(source,name,boundary,s.span,attr))
                for name in ('ps','ss','le','te'):
                    setattr(s,name,resample_curve(getattr(s,'master_'+name),len(getattr(s,name).r)))
    if od:
        for group in (result.sections,result.splitter_sections or []):
            for section in group:_diameter_section(section,diameter/2)
    if settings.shroud_area_cut_percent and settings.shroud_downstream_mode=='restore':
        _restore_downstream(base,result)
    # Data arrays describe the retained camber, not a regenerated beta distribution.
    for group,source in ((result.sections,base.sections),(result.splitter_sections or [],base.splitter_sections or [])):
        for section,original in zip(group,source):
            section.m=section.camber.meridional_distance.copy()
            x=section.camber.m_blade_norm
            source_span=section.camber.source_span
            for key in ('beta_m_deg','thickness'):
                values=np.array([np.interp(x,s.camber.m_blade_norm,getattr(s,key)) for s in source])
                value=(np.interp(x,original.camber.m_blade_norm,getattr(original,key)) if source_span is None else
                       _blend(values,np.array([s.span for s in source]),source_span))
                setattr(section,key,value)
            _validate_section(section)
    result.trim_report={'base_diameter_mm':base_diameter,'diameter_mm':diameter if od else base_diameter,
                        'reference_area_ratio':1-settings.shroud_area_cut_percent/100}
    return result


def _validate_section(s):
    # Source interpolation preserves joins; clipping must preserve them too.
    for a,ia,b,ib in ((s.master_le,0,s.master_ss,0),(s.master_le,-1,s.master_ps,0),
                      (s.master_te,0,s.master_ps,-1),(s.master_te,-1,s.master_ss,-1)):
        if np.linalg.norm(a.xyz[ia]-b.xyz[ib])>1e-6:
            raise ValueError('Impeller trim profile edges do not join.')
    for name in ('camber','master_ps','master_ss','master_le','master_te'):
        c=getattr(s,name)
        if not np.isfinite(c.xyz).all() or np.any(c.r<=0):raise ValueError('Invalid impeller trim profile.')
    from .checks import has_self_intersection
    curves=(s.master_le,s.master_ps,s.master_te,s.master_ss)
    chart=np.concatenate([np.column_stack((c.meridional_distance,c.theta_rad*np.mean(s.camber.r)))[sl]
        for c,sl in zip(curves,(slice(None,-1),slice(None,-1),slice(None,-1),slice(None,0,-1)))])
    chart=chart[np.r_[True,np.linalg.norm(np.diff(chart,axis=0),axis=1)>1e-10]]
    if has_self_intersection(chart):raise ValueError('Impeller trim profile self intersection or zero thickness.')
