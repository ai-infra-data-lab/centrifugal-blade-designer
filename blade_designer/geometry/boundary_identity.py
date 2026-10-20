"""Exact corresponding-parameter identity in the saved float64 coefficient model.

This does not certify physical geometry, source-fit uncertainty or a seam chart.
"""
from bisect import bisect_right
from collections.abc import Mapping
from copy import deepcopy
from fractions import Fraction
import numpy as np
from .boundary_gap import _boundary
from .contact_sources import surface_fingerprint
from .mesh_contacts import _positive_int
from .surface_injectivity import _range
from .role_seams import ROLES,SEAMS


class _ExactLimit(Exception):
    pass


def _fraction_text(value):
    """Decimal ratio without changing Python's process-wide int-string limit."""
    def integer_text(number):
        sign='-' if number<0 else '';number=abs(number);chunks=[]
        while number:
            number,chunk=divmod(number,10**9);chunks.append(chunk)
        if not chunks:return '0'
        return sign+str(chunks[-1])+''.join(f'{c:09d}' for c in reversed(chunks[:-1]))
    numerator=integer_text(value.numerator)
    return numerator if value.denominator==1 else numerator+'/'+integer_text(value.denominator)


class _Arithmetic:
    def __init__(self,bits):
        self.bits=bits;self.values=0

    def check(self,value):
        self.values+=1
        if max(value.numerator.bit_length(),value.denominator.bit_length())>self.bits:
            raise _ExactLimit
        return value

    def number(self,value):
        return self.check(Fraction(float(value)))


def _evaluate(curve,x,arithmetic):
    """de Boor using rational operations, no SciPy float evaluation or refit."""
    knots,degree,coefficients=curve
    index=len(coefficients)-1 if x==1 else bisect_right(knots,x)-1
    values=[list(coefficients[index-degree+j]) for j in range(degree+1)]
    check=arithmetic.check
    for level in range(1,degree+1):
        for j in range(degree,level-1,-1):
            left=index-degree+j
            numerator=check(x-knots[left]);denominator=check(knots[left+degree-level+1]-knots[left])
            if denominator<=0:raise ValueError('Invalid active rational knot interval.')
            alpha=check(numerator/denominator);remaining=check(1-alpha)
            values[j]=[check(check(remaining*a)+check(alpha*b)) for a,b in zip(values[j-1],values[j])]
    return values[degree]


def boundary_curve_identity(first,first_end,second,second_end,*,span_range=(0.,1.),
                            max_evaluations=8192,max_control_points=4096,max_fraction_bits=16384):
    """Decide exact identity on every common knot interval by polynomial degree.

    On each interval degree <=p, equality at p+1 distinct rational parameters
    proves polynomial identity in this exact input model. A nonzero witness
    proves difference at the SAME parameter, not different geometric point sets.
    Boundary curves must be C0; discontinuities are never silently joined.
    """
    for value,name in ((max_evaluations,'max_evaluations'),(max_control_points,'max_control_points'),
                       (max_fraction_bits,'max_fraction_bits')):_positive_int(value,name)
    bounds=_range(span_range);sources=[deepcopy(first),deepcopy(second)]
    curves=[_boundary(s,e) for s,e in zip(sources,(first_end,second_end))]
    same=(curves[0][1]==curves[1][1] and np.array_equal(curves[0][0],curves[1][0])
          and np.array_equal(curves[0][2],curves[1][2]))
    lo,hi=bounds;breaks=np.unique(np.r_[lo,hi,*[t[(t>lo)&(t<hi)] for t,_,_ in curves]])
    degree=max(c[1] for c in curves);required=2*(degree+1)*(len(breaks)-1)
    result={'span_range':bounds.tolist(),'source_fingerprints':[surface_fingerprint(s) for s in sources],
            'span_degrees':[c[1] for c in curves],'same_float64_boundary_representation':same,
            'common_intervals':len(breaks)-1,'required_evaluations':required,'checked_evaluations':0,
            'checked_intervals':0,'rational_values_checked':0,'max_evaluations':max_evaluations,
            'max_control_points':max_control_points,'max_fraction_bits':max_fraction_bits,
            'identity_decided':False,'same_parameter_curve_exact_model':None,'counterexample':None,
            'parameter_correspondence_assumed':True,'coordinates_modified':False,'seam_chart_ready':False,
            'input_generation_error_bounded':False,'physical_gap_certified':False,
            'roundoff_certified':False,'continuous_surface_certified':False,'whole_geometry_verified':False}
    if any(len(c)>max_control_points for _,_,c in curves):
        return {**result,'status':'RESOURCE_LIMIT','reason':'max_control_points'}
    if required>max_evaluations:return {**result,'status':'RESOURCE_LIMIT','reason':'max_evaluations'}
    arithmetic=_Arithmetic(max_fraction_bits)
    try:
        exact=[(tuple(arithmetic.number(x) for x in t),k,
                tuple(tuple(arithmetic.number(x) for x in pole) for pole in c)) for t,k,c in curves]
        points=[arithmetic.number(x) for x in breaks]
        for a,b in zip(points,points[1:]):
            for j in range(degree+1):
                x=arithmetic.check(a+arithmetic.check(arithmetic.check(b-a)*Fraction(j,degree)))
                values=[]
                for curve in exact:
                    values.append(_evaluate(curve,x,arithmetic));result['checked_evaluations']+=1
                difference=[arithmetic.check(u-v) for u,v in zip(*values)]
                if any(difference):
                    return {**result,'status':'EXACT_PARAMETER_CURVE_DIFFERENCE','reason':'nonzero_rational_witness',
                        'identity_decided':True,'same_parameter_curve_exact_model':False,
                        'rational_values_checked':arithmetic.values,
                        'counterexample':{'interval':[_fraction_text(a),_fraction_text(b)],'span':_fraction_text(x),
                            'first_exact_mm':list(map(_fraction_text,values[0])),'second_exact_mm':list(map(_fraction_text,values[1])),
                            'difference_exact_mm':list(map(_fraction_text,difference))}}
            result['checked_intervals']+=1
    except _ExactLimit:
        return {**result,'status':'RESOURCE_LIMIT','reason':'max_fraction_bits','rational_values_checked':arithmetic.values}
    return {**result,'status':'EXACT_SAME_PARAMETER_CURVE','reason':'piecewise_polynomial_identity',
            'identity_decided':True,'same_parameter_curve_exact_model':True,'rational_values_checked':arithmetic.values}


def role_boundary_curve_identity(surfaces,**options):
    """All four declared seams; never turn a partial decision into equality."""
    if not isinstance(surfaces,Mapping) or set(surfaces)!=set(ROLES):raise ValueError('All four role surfaces required.')
    sources=deepcopy(surfaces);seams=[]
    for a,ia,b,ib in SEAMS:
        seams.append({'first_role':a,'first_end':ia,'second_role':b,'second_end':ib,
                      'report':boundary_curve_identity(sources[a],ia,sources[b],ib,**options)})
    identities=[s['report']['same_parameter_curve_exact_model'] for s in seams]
    complete=all(x is not None for x in identities)
    identical=True if all(x is True for x in identities) else False if any(x is False for x in identities) else None
    return {'status':'EXACT_PARAMETER_CURVE_DIFFERENCE' if identical is False else
                    'EXACT_SAME_PARAMETER_CURVE' if identical is True else 'RESOURCE_LIMIT',
            'all_seams_identical_exact_model':identical,'scan_complete':complete,'seams':seams,
            'source_fingerprints':{r:surface_fingerprint(s) for r,s in sources.items()},
            'coordinates_modified':False,'seam_chart_ready':False,'physical_gap_certified':False,
            'continuous_surface_certified':False,'roundoff_certified':False,'whole_geometry_verified':False}
