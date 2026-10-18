"""One circular/elliptical arc tangent to sides, with bounded contact motion.

The side evaluators own the geometry/chart. No Qt, CAD or serialization imports.
"""
from dataclasses import dataclass
from numbers import Real
import numpy as np
from scipy.interpolate import make_interp_spline
from scipy.optimize import brentq

MAX_CONTACT_FRACTION = .15


def unit(vector):
    vector=np.asarray(vector,dtype=float)
    if vector.shape!=(2,) or not np.isfinite(vector).all():raise ValueError('Invalid planar edge tangent.')
    norm=np.linalg.norm(vector)
    if not np.isfinite(norm) or norm<=0:raise ValueError('Degenerate edge tangent.')
    return vector/norm


class SampledSide:
    def __init__(self,xy):
        xy=np.asarray(xy,dtype=float)
        if xy.ndim!=2 or xy.shape[1]!=2 or len(xy)<3 or not np.isfinite(xy).all():
            raise ValueError('Circular cap requires finite side samples.')
        self.spline=make_interp_spline(np.linspace(0,1,len(xy)),xy,k=min(3,len(xy)-1))
        self.slope=self.spline.derivative()
    def evaluate(self,parameter):return self.spline(parameter)
    def derivative(self,parameter):return self.slope(parameter)


@dataclass(frozen=True)
class CircularCap:
    center: np.ndarray
    radius: float
    start: np.ndarray
    end: np.ndarray
    sweep: float
    ps_parameter: float
    ss_parameter: float

    def evaluate(self,fraction):
        fraction=np.asarray(fraction,dtype=float)
        if self.radius==0:return np.broadcast_to(self.start,fraction.shape+(2,)).copy()
        angle=self.sweep*fraction;c=np.cos(angle);s=np.sin(angle)
        radial=self.start-self.center
        return self.center+np.stack((radial[0]*c-radial[1]*s,radial[0]*s+radial[1]*c),axis=-1)

    def direction(self,fraction):
        radial=self.evaluate(fraction)-self.center
        return np.sign(self.sweep)*np.stack((-radial[...,1],radial[...,0]),axis=-1)/self.radius

    def sample(self,count):
        if type(count) is not int or count<2:raise ValueError('At least two cap samples required.')
        points=self.evaluate(np.linspace(0,1,count));points[0]=self.start;points[-1]=self.end
        return points


def fit_circular_cap(ps,ss,leading,flow_direction):
    """Tangent circle, not a biarc; bounded contact search, no extrapolation.

    Hold one trial contact on a side. Circle centers are on its inward normal.
    For Q on the other side, r=|Q-P|²/(2 n.(Q-P)); solve (Q-C).Q'=0.
    Try either original contact first; only if needed try both contacts inside
    the first/last 15% of their normalized side parameter. Fail rather than weld.
    """
    edge=0. if leading else 1.
    points=[np.asarray(side.evaluate(edge)) for side in (ps,ss)]
    width=np.linalg.norm(points[1]-points[0])
    if not np.isfinite(width):raise ValueError('Non-finite circular cap width.')
    start,end=(points[1],points[0]) if leading else (points[0],points[1])
    if width==0:return CircularCap(start.copy(),0.,start.copy(),end.copy(),0.,edge,edge)
    outward=unit(flow_direction)*(-1 if leading else 1)
    sides=(ps,ss);away=1 if leading else -1
    parameter=lambda q:q if leading else 1-q
    candidates=[]
    for anchor_fraction in (0.,.002,.005,.01,.02,.04,.08,.12):
        for anchor_id in (0,1):
            anchor=sides[anchor_id];other=sides[1-anchor_id]
            contact=np.asarray(anchor.evaluate(parameter(anchor_fraction)))
            direction=unit(anchor.derivative(parameter(anchor_fraction)))*away
            normal=np.array([-direction[1],direction[0]])
            if np.dot(normal,points[1-anchor_id]-contact)<0:normal=-normal
            def geometry(q):
                target=np.asarray(other.evaluate(parameter(q)))
                delta=(target-contact)/width;projection=np.dot(normal,delta)
                if projection<=1e-12:return None
                radius=np.dot(delta,delta)/(2*projection)*width
                if not np.isfinite(radius) or not 1e-10*width<radius<=10*width:return None
                center=contact+radius*normal
                residual=np.dot((target-center)/radius,unit(other.derivative(parameter(q))))
                return center,radius,target,float(residual)
            grid=np.linspace(0,MAX_CONTACT_FRACTION,49)
            values=[geometry(q) for q in grid];roots=[]
            for q,value in zip(grid,values):
                if value is not None and abs(value[3])<=1e-10:roots.append(float(q))
            for lo,hi,a,b in zip(grid[:-1],grid[1:],values[:-1],values[1:]):
                if a is not None and b is not None and a[3]*b[3]<0:
                    def residual(q):
                        value=geometry(q)
                        if value is None:raise ValueError('Circular cap normal branch became invalid.')
                        return value[3]
                    try:roots.append(brentq(residual,lo,hi,xtol=1e-14,rtol=1e-14))
                    except ValueError:continue
            for q in roots:
                center,radius,target,residual=geometry(q)
                if abs(residual)>1e-9:continue
                contacts=[None,None];contacts[anchor_id]=contact;contacts[1-anchor_id]=target
                parameters=[None,None];parameters[anchor_id]=parameter(anchor_fraction);parameters[1-anchor_id]=parameter(q)
                tangents=[unit(side.derivative(u))*away for side,u in zip(sides,parameters)]
                start,end=(contacts[1],contacts[0]) if leading else (contacts[0],contacts[1])
                t0,t1=(-tangents[1],tangents[0]) if leading else (-tangents[0],tangents[1])
                a=(start-center)/radius;b=(end-center)/radius
                sign=np.sign(a[0]*t0[1]-a[1]*t0[0])
                sweep=np.arctan2(a[0]*b[1]-a[1]*b[0],np.dot(a,b))
                if sign*sweep<=0:sweep+=sign*2*np.pi
                if not 1e-8<abs(sweep)<2*np.pi-1e-8:continue
                cap=CircularCap(center,radius,start,end,float(sweep),*parameters)
                if min(np.dot(cap.direction(0),t0),np.dot(cap.direction(1),t1))<1-1e-8:continue
                if np.max((cap.evaluate(np.linspace(0,1,17))-(start+end)/2)@outward)<=width*1e-10:continue
                candidates.append((anchor_fraction+q,cap))
        if candidates:return min(candidates,key=lambda item:item[0])[1]
    raise ValueError('No single tangent circle found by the local contact search in the first/last 15% of PS/SS. Adjust the end thickness or blade angle.')


def contact_intervals(caps):
    result=[]
    for side in ('ps','ss'):
        lo=getattr(caps[True],side+'_parameter') if True in caps else 0.
        hi=getattr(caps[False],side+'_parameter') if False in caps else 1.
        if hi<=lo:raise ValueError('Circular LE/TE contact regions overlap.')
        result.append((lo,hi))
    return result


@dataclass(frozen=True)
class EllipticalCap:
    """An affine image of one tangent circle; derivatives use the same map."""
    circle: CircularCap
    origin: np.ndarray
    inverse: np.ndarray

    @property
    def ps_parameter(self):return self.circle.ps_parameter
    @property
    def ss_parameter(self):return self.circle.ss_parameter
    @property
    def start(self):return self.origin+self.inverse@self.circle.start
    @property
    def end(self):return self.origin+self.inverse@self.circle.end

    def evaluate(self,fraction):return self.origin+self.circle.evaluate(fraction)@self.inverse.T

    def direction(self,fraction):
        vector=self.circle.direction(fraction)@self.inverse.T
        return vector/np.linalg.norm(vector,axis=-1,keepdims=True)

    def sample(self,count):
        points=self.circle.sample(count)@self.inverse.T+self.origin
        points[0]=self.start;points[-1]=self.end
        return points


def fit_elliptical_cap(ps,ss,leading,flow_direction,ratio):
    """Scale the flow axis to a circle chart, solve both tangencies, map back.

    The axis along the end camber tangent has semi-axis ratio a/b=ratio.
    Nonsingular linear maps preserve the contact and tangent directions.
    Contacts obey the same bounded original-side search as circular caps.
    """
    if isinstance(ratio,(bool,np.bool_)) or not isinstance(ratio,Real) or not np.isfinite(ratio) or ratio<=0:
        raise ValueError('Ellipse ratio must be finite and > 0.')
    axis=unit(flow_direction);projector=np.outer(axis,axis)
    transform=np.eye(2)+(1/ratio-1)*projector
    inverse=np.eye(2)+(ratio-1)*projector
    edge=0. if leading else 1.
    origin=(ps.evaluate(edge)+ss.evaluate(edge))/2
    class TransformedSide:
        def __init__(self,side):self.side=side
        def evaluate(self,q):return (self.side.evaluate(q)-origin)@transform.T
        def derivative(self,q):return self.side.derivative(q)@transform.T
    circle=fit_circular_cap(TransformedSide(ps),TransformedSide(ss),leading,axis)
    return EllipticalCap(circle,origin,inverse)
