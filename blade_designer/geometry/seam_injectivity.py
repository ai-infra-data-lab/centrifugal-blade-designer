"""One common projection across two exactly matching source boundaries.

Numeric sufficient evidence only; no welding, export gate or roundoff proof.
"""
from collections import Counter
from copy import deepcopy
import numpy as np
from .boundary_gap import _boundary
from .surface_envelope import _control_net,_insert,_targets
from .surface_injectivity import _range
from .surface_diagnostics import spline_differentials
from .mesh_contacts import _nonnegative,_positive_int
from .contact_sources import surface_fingerprint


def seam_projection_injectivity(first,first_end,second,second_end,*,
                                first_width,second_width,reference_min_mm,monotonic_margin,
                                span_range=(0.,1.),refinements=0,max_cells=4096,projection_strategy='average'):
    """Check a continuous joined chart on (u,v) in [0,1] x [-1,1].

    Each xi width is a positive source-domain fraction. First side occupies
    negative v, second positive v. Same Span knots, degree AND boundary poles
    are required before any positive result. Geometrically equal but differently
    represented boundaries conservatively remain unresolved. Span correspondence
    is assumed, not established here. All cells use one fixed projection.
    'balanced_transverse' balances the two signed transverse directions only
    when selecting that projection; source derivatives/domain remain unchanged.
    """
    _nonnegative(reference_min_mm,'reference_min_mm');_nonnegative(monotonic_margin,'monotonic_margin')
    _positive_int(max_cells,'max_cells')
    if type(refinements) is not int or not 0<=refinements<=4:raise ValueError('refinements must be in [0,4].')
    if type(projection_strategy) is not str or projection_strategy not in ('average','balanced_transverse'):
        raise ValueError('Unknown projection_strategy.')
    for name,width in [('first_width',first_width),('second_width',second_width)]:
        _nonnegative(width,name)
        if not 0<width<=1:raise ValueError('Widths must be in (0,1].')
    span=_range(span_range);sources=[deepcopy(first),deepcopy(second)]
    boundaries=[_boundary(s,e) for s,e in zip(sources,(first_end,second_end))]
    same=(boundaries[0][1]==boundaries[1][1] and np.array_equal(boundaries[0][0],boundaries[1][0])
          and np.array_equal(boundaries[0][2],boundaries[1][2]))
    result={'span_range':span.tolist(),'ends':[first_end,second_end],
            'widths':[float(first_width),float(second_width)],'refinements':refinements,'max_cells':max_cells,
            'reference_min_mm':float(reference_min_mm),'monotonic_margin':float(monotonic_margin),
            'projection_strategy':projection_strategy,
            'source_fingerprints':[surface_fingerprint(s) for s in sources],
            'same_float64_boundary_representation':same,'parameter_correspondence_assumed':True,
            'numeric_injective':False,'projection':None,'cells':[],'required_cells':None,
            'min_symmetric_lower':None,'reference_sigma_mm':None,'coordinates_modified':False,
            'roundoff_certified':False,'continuous_surface_certified':False,'whole_geometry_verified':False}
    prepared=[]
    for side,(source,end,width) in enumerate(zip(sources,(first_end,second_end),(first_width,second_width))):
        inward=1 if end==0 else -1;edge=0. if end==0 else 1.
        xi=sorted((edge,edge+inward*width));ranges=[span,xi]
        if not xi[0]<xi[1]:raise ValueError('Width is not representable at this endpoint.')
        knots,degrees,net=_control_net(source);breaks=[]
        for t,k,(lo,hi) in zip(knots,degrees,ranges):
            if any(n>k for x,n in Counter(t).items() if 0<x<1):
                raise ValueError('Discontinuous source knots are unsupported.')
            selected=np.unique(np.r_[lo,t[(t>lo)&(t<hi)],hi])
            breaks.append(np.array(sorted(_targets(selected,selected,refinements))))
        scale=inward*width*(-1 if side==0 else 1)
        prepared.append((knots,degrees,net,breaks,edge,scale))
    if not same:return {**result,'status':'UNRESOLVED','reason':'boundary_representation_mismatch'}
    required=sum((len(b[0])-1)*(len(b[1])-1) for _,_,_,b,_,_ in prepared)
    result['required_cells']=required
    if required>max_cells:return {**result,'status':'RESOURCE_LIMIT','reason':'max_cells'}
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            references=[];span_length=span[1]-span[0]
            for source,(_,_,_,_,edge,scale) in zip(sources,prepared):
                d=spline_differentials(source,[span[0]+span_length/2],[edge],singular_mm2=0)
                references.append(np.column_stack((d.d_span[0,0]*span_length,d.d_xi[0,0]*scale)))
            reference=references[0]/2+references[1]/2
            if projection_strategy=='balanced_transverse':
                transverse=[a[:,1] for a in references];lengths=[float(np.linalg.norm(a)) for a in transverse]
                if min(lengths)<=reference_min_mm:
                    return {**result,'status':'UNRESOLVED','reason':'reference_transverse'}
                reference[:,1]=(transverse[0]/lengths[0]+transverse[1]/lengths[1])*(lengths[0]/4+lengths[1]/4)
            u,sigma,vt=np.linalg.svd(reference,full_matrices=False)
            result['reference_sigma_mm']=sigma.tolist()
            if sigma[-1]<=reference_min_mm:return {**result,'status':'UNRESOLVED','reason':'reference_rank'}
            projection=(vt.T/sigma)@u.T
            if not np.isfinite(projection).all():raise ValueError('Projection must be finite.')
            cells=[]
            for side,(knots,degrees,net,breaks,_,scale) in enumerate(prepared):
                for axis,values in enumerate(breaks):
                    k=degrees[axis]
                    knots[axis],net=_insert(knots[axis],net,k,axis,{x:k+1 if x in (0,1) else k for x in values})
                p,q=degrees
                for s0,s1 in zip(breaks[0],breaks[0][1:]):
                    i=int(np.searchsorted(knots[0],s0,side='right'))-1-p
                    for t0,t1 in zip(breaks[1],breaks[1][1:]):
                        j=int(np.searchsorted(knots[1],t0,side='right'))-1-q
                        local=net[i:i+p+1,j:j+q+1]
                        ds=(p*np.diff(local,axis=0)/(s1-s0)*span_length)@projection.T
                        dt=(q*np.diff(local,axis=1)/(t1-t0)*scale)@projection.T
                        a=float(ds[:,:,0].min());d=float(dt[:,:,1].min())
                        low=float(dt[:,:,0].min()/2+ds[:,:,1].min()/2)
                        high=float(dt[:,:,0].max()/2+ds[:,:,1].max()/2)
                        lower=float(a/2+d/2-np.hypot(a/2-d/2,max(abs(low),abs(high))))
                        if not np.isfinite([a,d,low,high,lower]).all():raise ValueError('Bounds must be finite.')
                        cells.append({'side':side,'span_range':[float(s0),float(s1)],
                            'xi_range':[float(t0),float(t1)],'diagonal_lower':[a,d],
                            'symmetric_off_interval':[low,high],'symmetric_lower':lower,
                            'numeric_positive':bool(lower>monotonic_margin)})
    except (FloatingPointError,np.linalg.LinAlgError) as exc:
        raise ValueError('Non-finite or failed seam projection arithmetic.') from exc
    met=all(c['numeric_positive'] for c in cells)
    return {**result,'status':'NUMERIC_INJECTIVE_ON_JOINED_CHART' if met else 'UNRESOLVED',
            'reason':'strong_monotonicity' if met else 'symmetric_bound_not_positive',
            'numeric_injective':met,'projection':projection.tolist(),'cells':cells,
            'min_symmetric_lower':min(c['symmetric_lower'] for c in cells)}
