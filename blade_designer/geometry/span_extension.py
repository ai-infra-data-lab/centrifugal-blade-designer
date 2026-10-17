"""Continue the last span segment to a casing; no Qt or file conventions.

Corresponding points continue linearly in cylindrical (Z, R, theta). The
meridional ray intersects analytic Line/Arc walls. Original sections are read
only, including the physical clearance Tip and its parameter-mapped stacking.
"""
from copy import deepcopy
import numpy as np
from ..models.geometry_3d import Curve3D
from ..models.meridional import ArcSegmentGeometry
from .checks import has_self_intersection


def _extend_curve(previous,tip,wall,tolerance):
    if not np.isfinite(previous.xyz).all() or not np.isfinite(tip.xyz).all():
        raise ValueError('Span extension requires finite coordinates.')
    if previous.xyz.shape!=tip.xyz.shape:
        # Cutoff trims each side at a different sample. Retain the physical
        # Tip samples and match the preceding side by local arc fraction.
        def fractions(curve):
            arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(curve.xyz,axis=0),axis=1))]
            if arc[-1]<=1e-12:raise ValueError('Span extension has a collapsed contour segment.')
            return arc/arc[-1]
        source,target=fractions(previous),fractions(tip)
        keep=np.r_[True,np.diff(source)>1e-14]
        previous=Curve3D(*(np.interp(target,source[keep],values[keep])
                           for values in (previous.r,previous.theta_rad,previous.z)))
    start=np.column_stack((tip.z,tip.r));delta=start-np.column_stack((previous.z,previous.r))
    a=np.einsum('ij,ij->i',delta,delta)
    if np.any(a<1e-18):raise ValueError('Span extension has a collapsed meridional span.')
    best=np.full(len(start),np.inf);distances=np.full(len(start),np.nan);offset=0.
    cross=lambda u,v:u[...,0]*v[...,1]-u[...,1]*v[...,0]
    for segment in wall.segments:
        if isinstance(segment,ArcSegmentGeometry):
            v=start-segment.center.zr;b=2*np.einsum('ij,ij->i',v,delta)
            c=np.einsum('ij,ij->i',v,v)-segment.radius**2;discriminant=b*b-4*a*c
            roots=[(-b+sign*np.sqrt(np.maximum(discriminant,0)))/(2*a) for sign in (-1,1)]
        else:
            denominator=cross(delta,segment.start_tangent)
            roots=[np.divide(cross(segment.start.zr-start,segment.start_tangent),denominator,
                             out=np.full(len(start),np.inf),where=np.abs(denominator)>1e-14)]
        for fraction in roots:
            # The physical Tip is sampled on chords. At a zero-clearance
            # endpoint it can lie a few microns outside the analytic arc.
            valid=np.isfinite(fraction)&(fraction>=-tolerance/np.sqrt(a))
            safe=np.where(valid,fraction,0.)
            point=start+safe[:,None]*delta
            if isinstance(segment,ArcSegmentGeometry):
                first=segment.start.zr-segment.center.zr;v=point-segment.center.zr
                angle=np.arctan2(cross(first,v),v@first)*(-1 if segment.clockwise else 1)
                angle=np.mod(angle,2*np.pi)
                angle=np.where(np.linalg.norm(point-segment.start.zr,axis=1)<1e-8,0.,angle)
                local=angle*segment.radius;valid&=discriminant>=0
            else:
                local=(point-segment.start.zr)@segment.start_tangent
            valid&=(local>=-1e-8)&(local<=segment.length+1e-8)&(safe<best)
            best[valid]=safe[valid];distances[valid]=offset+np.clip(local[valid],0,segment.length)
        offset+=segment.length
    if not np.isfinite(best).all():
        raise ValueError('Span extension does not intersect the Shroud in the outward direction.')
    zr=start+best[:,None]*delta
    theta=tip.theta_rad+best*(tip.theta_rad-previous.theta_rad)
    if np.any(zr[:,1]<=0) or not np.isfinite(theta).all():
        raise ValueError('Span extension requires finite coordinates and positive radius.')
    return Curve3D(zr[:,1],theta,zr[:,0],
                   None if tip.m_blade_norm is None else tip.m_blade_norm.copy(),distances)


def extend_tip_to_shroud(geometry):
    """Return one new section beyond the physical Tip, preserving input data."""
    if geometry.tip is None or len(geometry.sections)<2:
        raise ValueError('Span extension requires a clearance Tip and at least two sections.')
    previous,tip=geometry.sections[-2:]
    radii=[s.radius for s in geometry.shroud.segments if isinstance(s,ArcSegmentGeometry)]
    step=float(np.max(np.diff(geometry.tip.casing_m)))
    tolerance=1e-8+(step*step/(2*min(radii)) if radii else 0.)
    result=deepcopy(tip)
    for name in ('camber','ps','ss','le','te','master_ps','master_ss','master_le','master_te'):
        setattr(result,name,_extend_curve(getattr(previous,name),getattr(tip,name),geometry.shroud,tolerance))
    if np.any(np.diff(result.camber.meridional_distance)<=0):
        raise ValueError('Span extension reverses along the Shroud.')
    curves=[result.master_le,result.master_ps,result.master_te,result.master_ss]
    for edge,a,b,index in ((curves[0],curves[3],curves[1],0),(curves[2],curves[1],curves[3],-1)):
        if not (np.allclose(edge.xyz[0],a.xyz[index],rtol=0,atol=1e-8)
                and np.allclose(edge.xyz[-1],b.xyz[index],rtol=0,atol=1e-8)):
            raise ValueError('Span extension has disconnected contour junctions.')
    chart=np.concatenate([np.column_stack((c.meridional_distance,c.theta_rad*np.mean(result.camber.r)))[sl]
                          for c,sl in zip(curves,(slice(None,-1),slice(None,-1),slice(None,-1),slice(None,0,-1)))])
    chart=chart[np.r_[True,np.linalg.norm(np.diff(chart,axis=0),axis=1)>1e-12]]
    if len(chart)>1 and np.linalg.norm(chart[-1]-chart[0])<1e-12:chart=chart[:-1]
    if len(chart)<3 or not np.isfinite(chart).all() or has_self_intersection(chart):
        raise ValueError('Span extension creates a collapsed or self-intersecting Shroud contour.')
    result.m=result.camber.meridional_distance.copy()
    return result
