"""Tangent caps constrained by their completed streamwise nose positions."""
from numbers import Real
import numpy as np
from scipy.interpolate import PPoly, PchipInterpolator, CubicHermiteSpline, make_interp_spline
from scipy.optimize import least_squares
from .tangent_arcs import CircularCap, EllipticalCap, unit

MAX_POSITIONED_CONTACT_FRACTION = .45
COORDINATE_GEOMETRY_VERSION = 'rounded-nose-1'


class CutoffSideSpline:
    """Keep cylinder-cut distances monotone; cubic theta remains unchanged."""
    def __init__(self, coordinates, values):
        self.distance_spline=PchipInterpolator(coordinates,values[:,0])
        self.theta=make_interp_spline(coordinates,values[:,1],k=3)

    def __call__(self,q):
        return np.stack((self.distance_spline(q),self.theta(q)),axis=-1)

    def derivative(self):
        distance=self.distance_spline.derivative();theta=self.theta.derivative()
        return lambda q:np.stack((distance(q),theta(q)),axis=-1)


def cap_extrema_parameters(cap):
    """Exact stationary parameters of meridional distance, not sampled minima."""
    circle = getattr(cap, 'circle', cap)
    if circle.radius == 0:
        return np.array([0., 1.])
    radial = circle.start - circle.center
    transform = getattr(cap, 'inverse', np.eye(2))
    a = float(transform[0] @ radial)
    b = float(transform[0] @ np.array([-radial[1], radial[0]]))
    angle = np.arctan2(b, a)
    parameters = [0., 1.]
    for turn in range(-3, 4):
        fraction = (angle + turn * np.pi) / circle.sweep
        if 0 < fraction < 1:
            parameters.append(float(fraction))
    return np.unique(parameters)


def sample_positioned_cap(cap, count, leading):
    """Keep master point count while including exact streamwise extrema."""
    extrema=cap_extrema_parameters(cap)
    values=cap.evaluate(extrema)[:,0]
    nose=float(extrema[np.argmin(values) if leading else np.argmax(values)])
    middle=count//2
    if 0<nose<1:
        if count<3:raise ValueError('A finite rounded cap needs at least three points to retain its nose and both joins.')
        center=middle/(count-1)
        left=nose/center;right=(1-nose)/(1-center)
        middle_slope=2*left*right/(left+right)
        mapping=CubicHermiteSpline([0.,center,1.],[0.,nose,1.],[left,middle_slope,right])
        parameters=mapping(np.linspace(0.,1.,count))
        parameters[middle]=nose
        used={middle}
    else:
        parameters=np.linspace(0.,1.,count);used=set()
    for fraction in extrema[1:-1]:
        if fraction==nose:continue
        available = [i for i in range(1, count - 1) if i not in used]
        if not available:
            raise ValueError('Too few cap points to retain its streamwise extrema.')
        index = min(available, key=lambda i: abs(parameters[i] - fraction))
        parameters[index] = fraction
        used.add(index)
    points = cap.evaluate(np.sort(parameters))
    points[0], points[-1] = cap.start, cap.end
    return points


def side_distance_extrema(spline, interval):
    polynomial = (spline.distance_spline if isinstance(spline,CutoffSideSpline)
                  else PPoly.from_spline((spline.t, spline.c[:, 0], spline.k)))
    roots = polynomial.derivative().roots(extrapolate=False)
    lo, hi = interval
    roots = roots[np.isfinite(roots) & (roots > lo) & (roots < hi)]
    return polynomial(np.r_[lo, roots, hi])


def fit_positioned_cap(ps, ss, leading, flow_direction, nose_distance, ratio=1.):
    """One tangent circle/ellipse with its streamwise extremum at the target.

    Unknowns are the two original-side contact parameters. The first normal
    and incidence at the second contact determine the circle. Solve the second
    tangency and the exact projected nose, in a circle chart for an ellipse.
    Camber, side distributions and the finite contact search remain unchanged.
    """
    if (isinstance(ratio,(bool,np.bool_)) or not isinstance(ratio,Real)
            or not np.isfinite(ratio) or ratio<=0 or not np.isfinite(nose_distance)):
        raise ValueError('Positioned ellipse ratio and nose distance must be finite; ratio must be > 0.')
    edge=0. if leading else 1.
    origin=(ps.evaluate(edge)+ss.evaluate(edge))/2
    width=float(np.linalg.norm(ps.evaluate(edge)-ss.evaluate(edge)))
    if width==0:
        return CircularCap(origin.copy(),0.,origin.copy(),origin.copy(),0.,edge,edge)
    axis=unit(flow_direction);projector=np.outer(axis,axis)
    transform=np.eye(2)+(1/ratio-1)*projector
    inverse=np.eye(2)+(ratio-1)*projector
    parameter=lambda q:q if leading else 1-q
    away=1 if leading else -1
    def point(side,q):return transform@(side.evaluate(q)-origin)
    def tangent(side,q):return unit(transform@side.derivative(q))*away
    def geometry(values):
        u,v=map(parameter,values)
        p,q=point(ps,u),point(ss,v)
        t=tangent(ps,u);normal=np.array([-t[1],t[0]])
        if normal@(point(ss,edge)-p)<0:normal=-normal
        delta=q-p;projection=float(normal@delta)
        if projection<=1e-14*width:return None
        radius=float(delta@delta/(2*projection));center=p+radius*normal
        return u,v,p,q,center,radius
    def residual(values):
        data=geometry(values)
        if data is None:return np.array([1e3+values[0],1e3+values[1]])
        u,v,p,q,center,radius=data
        nose=origin[0]+inverse[0]@center+(-1 if leading else 1)*radius*np.linalg.norm(inverse[0])
        return np.array([(q-center)@tangent(ss,v)/radius,(nose-nose_distance)/width])
    speed=max(abs(ps.derivative(edge)[0]),abs(ss.derivative(edge)[0]),width)
    guess=min(.1,max(.001,width*max(1.,ratio)/speed))
    for seed in (guess,.005,.02,.06,.12):
        result=least_squares(residual,[seed,seed],bounds=(0.,MAX_POSITIONED_CONTACT_FRACTION),
                             xtol=1e-12,ftol=1e-12,gtol=1e-12,max_nfev=100)
        if not result.success or np.max(np.abs(residual(result.x)))>1e-10:continue
        u,v,p,q,center,radius=geometry(result.x)
        if not 1e-10*width<radius<=10*width:continue
        start,end=(q,p) if leading else (p,q)
        t0,t1=(-tangent(ss,v),tangent(ps,u)) if leading else (-tangent(ps,u),tangent(ss,v))
        a=(start-center)/radius;b=(end-center)/radius
        sign=np.sign(a[0]*t0[1]-a[1]*t0[0])
        sweep=np.arctan2(a[0]*b[1]-a[1]*b[0],a@b)
        if sign*sweep<=0:sweep+=sign*2*np.pi
        if not 1e-8<abs(sweep)<2*np.pi-1e-8:continue
        circle=CircularCap(center,radius,start,end,float(sweep),u,v)
        if min(circle.direction(0)@t0,circle.direction(1)@t1)<1-1e-8:continue
        cap=EllipticalCap(circle,origin,inverse)
        extrema=cap.evaluate(cap_extrema_parameters(cap))[:,0]
        actual=np.min(extrema) if leading else np.max(extrema)
        if abs(actual-nose_distance)>max(1e-9,width*1e-10):continue
        return cap
    raise ValueError('LE/TE positioning: no single tangent cap fits the specified nose within the local 45% contact region.')
