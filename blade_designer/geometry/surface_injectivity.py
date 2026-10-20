"""Sufficient injectivity evidence on one convex parameter rectangle.

One fixed planar projection and positive symmetric derivative bound establish
strong monotonicity in real arithmetic. Float operations are not certified.
Unresolved evidence does not imply a fold. Cross-role seams are not proved.
"""
from collections import Counter
from copy import deepcopy
import numpy as np
from .surface_envelope import _control_net,_insert,_targets
from .surface_diagnostics import spline_differentials
from .mesh_contacts import _nonnegative,_positive_int
from .contact_sources import source_triangle_patch,surface_fingerprint


def _range(values):
    a=np.asarray(values)
    if (a.shape!=(2,) or not np.isrealobj(a) or not np.issubdtype(a.dtype,np.number)
            or not np.isfinite(a).all() or not 0<=a[0]<a[1]<=1):
        raise ValueError('Parameter ranges must be finite increasing real pairs within [0,1].')
    return a.astype(float)


def surface_projection_injectivity(surface,*,reference_min_mm,monotonic_margin,
                                    span_range=(0.,1.),xi_range=(0.,1.),refinements=0,max_cells=4096):
    """Bound the projected symmetric derivative on every selected Bezier cell.

    Center derivatives define a fixed left inverse of the normalized-domain
    3x2 derivative. Its rank threshold is in mm; monotonic_margin is unitless.
    Continuous C0 splines are allowed using piecewise derivatives. No refit,
    change of chart between cells, or inference from a positive Jacobian.
    """
    _nonnegative(reference_min_mm,'reference_min_mm');_nonnegative(monotonic_margin,'monotonic_margin')
    _positive_int(max_cells,'max_cells')
    if type(refinements) is not int or not 0<=refinements<=4:raise ValueError('refinements must be in [0,4].')
    ranges=[_range(span_range),_range(xi_range)]
    knots,degrees,net=_control_net(surface);breaks=[]
    for t,k,(lo,hi) in zip(knots,degrees,ranges):
        if any(n>k for x,n in Counter(t).items() if 0<x<1):
            raise ValueError('Discontinuous source knots are unsupported.')
        selected=np.unique(np.r_[lo,t[(t>lo)&(t<hi)],hi])
        breaks.append(np.array(sorted(_targets(selected,selected,refinements))))
    required=(len(breaks[0])-1)*(len(breaks[1])-1)
    result={'span_range':ranges[0].tolist(),'xi_range':ranges[1].tolist(),
            'reference_min_mm':float(reference_min_mm),'monotonic_margin':float(monotonic_margin),
            'required_cells':required,'max_cells':max_cells,'refinements':refinements,
            'numeric_injective':False,'projection':None,'cells':[],
            'min_symmetric_lower':None,'reference_sigma_mm':None,
            'continuous_surface_certified':False,'roundoff_certified':False,
            'whole_geometry_verified':False}
    if required>max_cells:return {**result,'status':'RESOURCE_LIMIT','reason':'max_cells'}
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            center=[lo+(hi-lo)/2 for lo,hi in ranges]
            sample=spline_differentials(surface,[center[0]],[center[1]],singular_mm2=0)
            lengths=np.array([hi-lo for lo,hi in ranges])
            reference=np.column_stack((sample.d_span[0,0]*lengths[0],sample.d_xi[0,0]*lengths[1]))
            u,sigma,vt=np.linalg.svd(reference,full_matrices=False)
            result['reference_sigma_mm']=sigma.tolist()
            if sigma[-1]<=reference_min_mm:
                return {**result,'status':'UNRESOLVED','reason':'reference_rank'}
            projection=(vt.T/sigma)@u.T
            if not np.isfinite(projection).all():raise ValueError('Projection must be finite.')
            for axis,values in enumerate(breaks):
                k=degrees[axis]
                knots[axis],net=_insert(knots[axis],net,k,axis,{x:k+1 if x in (0,1) else k for x in values})
            cells=[];p,q=degrees
            for s0,s1 in zip(breaks[0],breaks[0][1:]):
                i=int(np.searchsorted(knots[0],s0,side='right'))-1-p
                for t0,t1 in zip(breaks[1],breaks[1][1:]):
                    j=int(np.searchsorted(knots[1],t0,side='right'))-1-q
                    local=net[i:i+p+1,j:j+q+1]
                    ds=(p*np.diff(local,axis=0)/(s1-s0)*lengths[0])@projection.T
                    dt=(q*np.diff(local,axis=1)/(t1-t0)*lengths[1])@projection.T
                    a=float(ds[:,:,0].min());d=float(dt[:,:,1].min())
                    off_low=float(dt[:,:,0].min()/2+ds[:,:,1].min()/2)
                    off_high=float(dt[:,:,0].max()/2+ds[:,:,1].max()/2)
                    b=max(abs(off_low),abs(off_high))
                    lower=float(a/2+d/2-np.hypot(a/2-d/2,b))
                    if not np.isfinite([a,d,b,lower]).all():raise ValueError('Projected derivative bounds must be finite.')
                    cells.append({'span_range':[float(s0),float(s1)],'xi_range':[float(t0),float(t1)],
                        'diagonal_lower':[a,d],'symmetric_off_interval':[off_low,off_high],
                        'symmetric_lower':lower,'numeric_positive':bool(lower>monotonic_margin)})
    except (FloatingPointError,np.linalg.LinAlgError) as exc:
        raise ValueError('Non-finite or failed projection arithmetic.') from exc
    lower=min(c['symmetric_lower'] for c in cells);met=all(c['numeric_positive'] for c in cells)
    return {**result,'status':'NUMERIC_INJECTIVE_ON_RECTANGLE' if met else 'UNRESOLVED',
            'reason':'strong_monotonicity' if met else 'symmetric_bound_not_positive',
            'numeric_injective':met,'projection':projection.tolist(),'cells':cells,
            'min_symmetric_lower':lower}


def local_source_pair_injectivity(surfaces,envelope,first_face,second_face,*,
                                   reference_min_mm,monotonic_margin,refinements=0,max_cells=4096):
    """Sufficient evidence for same-role neighboring source triangles only.

    The enclosing rectangle can contain additional source cells. Positivity
    must hold on the entire rectangle with one common projection. Different
    roles require a seam chart and remain unresolved, even if both are regular.
    Existing self-contact reports and export decisions are never rewritten.
    """
    _nonnegative(reference_min_mm,'reference_min_mm');_nonnegative(monotonic_margin,'monotonic_margin')
    _positive_int(max_cells,'max_cells')
    if type(refinements) is not int or not 0<=refinements<=4:raise ValueError('refinements must be in [0,4].')
    patches=[source_triangle_patch(envelope,i) for i in (first_face,second_face)]
    if first_face==second_face:raise ValueError('Distinct neighboring source triangles are required.')
    faces=envelope['mesh']['faces']
    if not set(faces[first_face])&set(faces[second_face]):raise ValueError('A shared-ID neighboring pair is required.')
    snapshots={}
    for patch in patches:
        role=patch['role']
        try:snapshots[role]=deepcopy(surfaces[role])
        except (KeyError,TypeError) as exc:raise ValueError('Selected source roles are required.') from exc
        if surface_fingerprint(snapshots[role])!=envelope.get('source_fingerprints',{}).get(role):
            raise ValueError('Source surface changed or lacks a recorded identity.')
    result={'patches':patches,'source_identity_checked':True,'projection_report':None,
            'expected_parameter_contact_only':False,'roundoff_certified':False,
            'continuous_surface_certified':False,'whole_geometry_verified':False}
    if patches[0]['role']!=patches[1]['role']:
        return {**result,'status':'UNRESOLVED','reason':'cross_role_requires_seam_chart'}
    ranges={key:[min(p[key][0] for p in patches),max(p[key][1] for p in patches)]
            for key in ('span_range','xi_range')}
    report=surface_projection_injectivity(snapshots[patches[0]['role']],**ranges,
        reference_min_mm=reference_min_mm,monotonic_margin=monotonic_margin,
        refinements=refinements,max_cells=max_cells)
    return {**result,'status':report['status'],'reason':report['reason'],'projection_report':report,
            'expected_parameter_contact_only':report['numeric_injective']}
