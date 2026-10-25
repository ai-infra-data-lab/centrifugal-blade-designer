"""A numeric proposal for a periodic cut; native CAD must certify its clearance.

This changes the cutting tool, never the blade coordinates. The reference phase
is fitted in physical R/Z, not in independently normalized Hub/Tip distances.
"""
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import RBFInterpolator


@dataclass
class SectorPhase:
    reference: object
    origin: np.ndarray
    scale: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    offset: float
    pitch: float
    sample_margin_rad: float

    def __call__(self, rz):
        values=np.asarray(rz,dtype=float)
        if values.ndim!=2 or values.shape[1]!=2 or not np.isfinite(values).all():
            raise ValueError('Finite R/Z query points are required.')
        # Constant continuation outside the blade bounding rectangle. The CAD
        # tool is a smooth interpolant of samples of this proposal, checked anew.
        query=np.clip((values-self.origin)/self.scale,self.lower,self.upper)
        return self.reference(query).reshape(-1)+self.offset


def blade_following_phase(groups, blade_count):
    if type(blade_count) is not int or blade_count<3:
        raise ValueError('Blade-following sectors require at least three main blades.')
    groups=list(groups)
    if not groups or groups[0][0]!='main':raise ValueError('Main blade coordinates are required first.')
    reference_points=[];reference_angles=[];all_points=[]
    anchor=None
    for name,sections in groups:
        if not sections:raise ValueError('Empty blade section group.')
        for section in sections:
            curves={}
            for role in ('le','ps','te','ss'):
                points=np.asarray(section[role],dtype=float)
                if points.ndim!=2 or points.shape[1]!=3 or len(points)<2 or not np.isfinite(points).all():
                    raise ValueError('Invalid blade coordinates for periodic cut.')
                if np.any(np.hypot(points[:,0],points[:,1])<=0):raise ValueError('Blade points must be off the rotation axis.')
                all_points.append(points)
                if role in ('ps','ss'):
                    xi=np.asarray(section.get(role+'_xi',np.linspace(0,1,len(points))),dtype=float)
                    if xi.shape!=(len(points),) or not np.isfinite(xi).all() or np.any(np.diff(xi)<=0):
                        raise ValueError('Strictly increasing blade correspondence is required.')
                    curves[role]=np.column_stack([np.interp(np.linspace(xi[0],xi[-1],33),xi,points[:,i]) for i in range(3)])
            if name=='main':
                center=(curves['ps']+curves['ss'])/2
                theta=np.unwrap(np.arctan2(center[:,1],center[:,0]))
                if anchor is None:anchor=float(theta[0])
                theta+=2*np.pi*round((anchor-float(theta[0]))/(2*np.pi))
                reference_points.extend(np.column_stack((np.hypot(center[:,0],center[:,1]),center[:,2])))
                reference_angles.extend(theta)
    rz=np.asarray(reference_points);angles=np.asarray(reference_angles)
    origin=rz.min(axis=0);scale=np.maximum(np.ptp(rz,axis=0),1.)
    normalized=(rz-origin)/scale
    unique,inverse=np.unique(normalized,axis=0,return_inverse=True)
    sums=np.bincount(inverse,weights=angles);counts=np.bincount(inverse)
    means=sums/counts
    if np.max(np.abs(angles-means[inverse]))>1e-6:
        raise ValueError('Multiple main-blade phases at identical R/Z; no single-valued boundary proposed.')
    reference=RBFInterpolator(unique,means,kernel='linear',degree=0,smoothing=1e-8)
    pitch=2*np.pi/blade_count
    phase=SectorPhase(reference,origin,scale,normalized.min(axis=0),normalized.max(axis=0),0.,pitch,0.)
    residuals=[]
    for points in all_points:
        estimate=phase(np.column_stack((np.hypot(points[:,0],points[:,1]),points[:,2])))
        theta=estimate+np.arctan2(np.sin(np.arctan2(points[:,1],points[:,0])-estimate),
                                 np.cos(np.arctan2(points[:,1],points[:,0])-estimate))
        residuals.extend(theta-estimate)
    low,high=float(np.min(residuals)),float(np.max(residuals))
    if high-low>=pitch:raise ValueError('No common one-pitch gap for the selected main/splitter set.')
    phase.offset=(low+high-pitch)/2
    phase.sample_margin_rad=(pitch-(high-low))/2
    return phase
