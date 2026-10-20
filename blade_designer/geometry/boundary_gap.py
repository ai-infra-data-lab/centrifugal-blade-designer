"""Corresponding-Span boundary curve envelopes, not seam topology approval."""
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
import numpy as np
from scipy.interpolate import BSpline
from .surface_envelope import _control_net,_insert,_targets
from .mesh_contacts import _nonnegative,_positive_int
from .role_seams import ROLES,SEAMS
from .contact_sources import surface_fingerprint


def _boundary(surface,end):
    if type(end) is not int or end not in (0,-1):raise ValueError('Boundary end must be 0 or -1.')
    knots,degrees,net=_control_net(surface);t=knots[0];k=degrees[0]
    if any(n>k for x,n in Counter(t).items() if 0<x<1):
        raise ValueError('Discontinuous Span boundary curves are unsupported.')
    return t,k,net[:,end].copy()


def _elevate(poles,target):
    while len(poles)-1<target:
        degree=len(poles)-1;weight=np.arange(1,degree+1)[:,None]/(degree+1)
        poles=np.concatenate((poles[:1],weight*poles[:-1]+(1-weight)*poles[1:],poles[-1:]))
    return poles


def boundary_gap_envelope(first,first_end,second,second_end,*,gap_tolerance_mm,
                           span_range=(0.,1.),refinements=0,max_intervals=2048):
    """Bound |C_first(s)-C_second(s)| at corresponding Span parameters.

    Extract clamped xi endpoints, align Span Bezier intervals, elevate degree
    1..3 if needed and use the convex hull of difference poles. Within a gap
    budget is not exact G0 equality, G1 or an injective joined surface chart.
    """
    _nonnegative(gap_tolerance_mm,'gap_tolerance_mm');_positive_int(max_intervals,'max_intervals')
    if type(refinements) is not int or not 0<=refinements<=4:raise ValueError('refinements must be in [0,4].')
    bounds=np.asarray(span_range)
    if (bounds.shape!=(2,) or not np.isrealobj(bounds) or not np.issubdtype(bounds.dtype,np.number)
            or not np.isfinite(bounds).all() or not 0<=bounds[0]<bounds[1]<=1):
        raise ValueError('span_range must be a finite increasing real pair within [0,1].')
    lo,hi=bounds.astype(float)
    curves=[_boundary(first,first_end),_boundary(second,second_end)]
    identical=(curves[0][1]==curves[1][1] and np.array_equal(curves[0][0],curves[1][0])
               and np.array_equal(curves[0][2],curves[1][2]))
    selected=[np.unique(np.r_[lo,t[(t>lo)&(t<hi)],hi]) for t,_,_ in curves]
    breaks=np.array(sorted(_targets(*selected,refinements)))
    result={'span_range':[float(lo),float(hi)],'gap_tolerance_mm':float(gap_tolerance_mm),
        'refinements':refinements,'max_intervals':max_intervals,'required_intervals':len(breaks)-1,
        'intervals':[],'max_upper_mm':None,'sample_max_mm':None,'numeric_within_tolerance':False,
        'same_float64_boundary_representation':identical,'span_degrees':[c[1] for c in curves],
        'parameter_correspondence_assumed':True,'seam_chart_ready':False,
        'roundoff_certified':False,'continuous_surface_certified':False,'whole_geometry_verified':False}
    if len(breaks)-1>max_intervals:return {**result,'status':'RESOURCE_LIMIT'}
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            aligned=[];evaluators=[]
            for t,k,c in curves:
                evaluators.append(BSpline(t,c,k))
                t,c=_insert(t,c,k,0,{x:k+1 if x in (0,1) else k for x in breaks})
                aligned.append((t,k,c))
            intervals=[];degree=max(c[1] for c in curves)
            for s0,s1 in zip(breaks,breaks[1:]):
                controls=[]
                for t,k,c in aligned:
                    start=int(np.searchsorted(t,s0,side='right'))-1-k
                    controls.append(_elevate(c[start:start+k+1],degree))
                upper=float(np.linalg.norm(controls[0]-controls[1],axis=1).max())
                query=[s0,s0+(s1-s0)/2,s1]
                sample=float(np.linalg.norm(evaluators[0](query)-evaluators[1](query),axis=1).max())
                if not np.isfinite([upper,sample]).all():raise ValueError('Boundary gap arithmetic must be finite.')
                intervals.append({'span_range':[float(s0),float(s1)],'upper_mm':upper,'sample_max_mm':sample,
                    'sample_exceeds_upper':bool(sample>upper),'numeric_within_tolerance':bool(max(upper,sample)<=gap_tolerance_mm)})
    except FloatingPointError as exc:raise ValueError('Non-finite boundary gap arithmetic.') from exc
    within=all(i['numeric_within_tolerance'] for i in intervals)
    upper=max(i['upper_mm'] for i in intervals);sample=max(i['sample_max_mm'] for i in intervals)
    return {**result,'status':'GAP_OBSERVED' if sample>gap_tolerance_mm else
            'NUMERIC_WITHIN_GAP_TOLERANCE' if within else 'UNRESOLVED',
            'intervals':intervals,'max_upper_mm':upper,'sample_max_mm':sample,
            'sample_upper_violations':sum(i['sample_exceeds_upper'] for i in intervals),
            'numeric_within_tolerance':within}


def role_boundary_gap_envelope(surfaces,*,gap_tolerance_mm,span_range=(0.,1.),
                               refinements=0,max_intervals=2048):
    """Read-only declared LE/PS/TE/SS seam checks; no welding or reparameterization."""
    if not isinstance(surfaces,Mapping) or set(surfaces)!=set(ROLES):
        raise ValueError('All four role spline surfaces are required.')
    snapshots=deepcopy(surfaces);seams=[]
    for a,ia,b,ib in SEAMS:
        report=boundary_gap_envelope(snapshots[a],ia,snapshots[b],ib,gap_tolerance_mm=gap_tolerance_mm,
                                    span_range=span_range,refinements=refinements,max_intervals=max_intervals)
        seams.append({'first_role':a,'first_end':ia,'second_role':b,'second_end':ib,'report':report})
    within=all(s['report']['numeric_within_tolerance'] for s in seams)
    complete=all(s['report']['status']!='RESOURCE_LIMIT' for s in seams)
    observed=any(s['report']['status']=='GAP_OBSERVED' for s in seams)
    return {'status':'GAP_OBSERVED' if observed else 'RESOURCE_LIMIT' if not complete else
            'NUMERIC_WITHIN_GAP_TOLERANCE' if within else 'UNRESOLVED',
            'all_seams_within_tolerance':within,'scan_complete':complete,'seams':seams,
            'source_fingerprints':{r:surface_fingerprint(snapshots[r]) for r in ROLES},
            'source_coordinates_modified':False,'parameter_correspondence_assumed':True,
            'seam_chart_ready':False,'roundoff_certified':False,'continuous_surface_certified':False,
            'whole_geometry_verified':False,
            'unchecked':['physical Span correspondence','exact G0 for nonzero gaps','G1/normal continuity',
                         'one-sided seam neighborhoods and joined chart injectivity','CAD/STEP final seams']}
