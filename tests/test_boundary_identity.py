"""Exact input-model identity; no tolerance-based welding or geometric-set claim."""
from copy import deepcopy
from fractions import Fraction
from decimal import Decimal
import json
import sys
import numpy as np
import pytest
from scipy.interpolate import BSpline
from blade_designer.geometry.boundary_identity import boundary_curve_identity,role_boundary_curve_identity
from blade_designer.geometry.boundary_identity import _fraction_text,_Arithmetic
from blade_designer.geometry.boundary_gap import boundary_gap_envelope
from blade_designer.geometry.surface_evaluation import SplineSurface
from test_seam_injectivity import bezier
from test_seam_contact_refinement import fixture


def line(degree=1):
    net=np.zeros((degree+1,2,3));net[:,:,0]=[0,1]
    net[:,:,1]=np.array([3*j/degree for j in range(degree+1)])[:,None]
    return bezier(net)


def check(a,b,**options):
    return boundary_curve_identity(a,0,b,0,**options)


@pytest.mark.parametrize('degrees',[(1,2),(1,3),(2,1),(2,3),(3,1),(3,2)])
def test_exact_same_line_with_different_degrees_is_not_a_gap(degrees):
    a,b=[line(d) for d in degrees];before=deepcopy((a.across.c,b.across.c))
    r=check(a,b)
    assert r['status']=='EXACT_SAME_PARAMETER_CURVE' and r['same_parameter_curve_exact_model']
    assert not r['same_float64_boundary_representation'] and r['identity_decided']
    assert r['checked_evaluations']==r['required_evaluations']
    assert not r['physical_gap_certified'] and not r['seam_chart_ready'] and not r['whole_geometry_verified']
    for s,old in zip((a,b),before):np.testing.assert_array_equal(s.across.c,old)


@pytest.mark.parametrize('knot',[.125,.5,.75])
def test_exact_knot_insertion_keeps_the_curve_but_changes_representation(knot):
    a=line();b=deepcopy(a);b.across=b.across.insert_knot(knot)
    r=check(a,b)
    assert r['same_parameter_curve_exact_model'] and not r['same_float64_boundary_representation']
    assert r['common_intervals']==2


def test_hidden_cubic_difference_cannot_pass_because_three_old_samples_match():
    a=line(3);b=deepcopy(a);b.across.c[:,:,2]=np.array([0,1,-1,0])[:,None]
    np.testing.assert_array_equal(a.evaluate_grid([0,.5,1],[0]),b.evaluate_grid([0,.5,1],[0]))
    assert boundary_gap_envelope(a,0,b,0,gap_tolerance_mm=.001)['status']=='UNRESOLVED'
    r=check(a,b);w=r['counterexample']
    assert r['status']=='EXACT_PARAMETER_CURVE_DIFFERENCE' and r['identity_decided']
    assert w['span']=='1/3' and Fraction(w['difference_exact_mm'][2])==Fraction(-2,9)
    assert not r['same_parameter_curve_exact_model']


def test_one_ulp_gap_has_an_exact_nonzero_witness_without_any_tolerance():
    a=line();b=line();a.across.c[:,:,2]=1;b.across.c[:,:,2]=np.nextafter(1.,2.)
    r=check(a,b)
    assert Fraction(r['counterexample']['difference_exact_mm'][2])==Fraction(-1,2**52)
    assert not r['same_parameter_curve_exact_model'] and not r['physical_gap_certified']


def test_subnormal_difference_is_preserved_by_exact_conversion():
    a=line();b=line();b.across.c[:,:,2]=np.nextafter(0.,1.)
    r=check(a,b)
    assert Fraction(r['counterexample']['difference_exact_mm'][2])==Fraction(-1,2**1074)


def test_difference_larger_than_float_max_is_reported_as_rational_strings():
    a=line();b=line();a.across.c[:,:,2]=1e308;b.across.c[:,:,2]=-1e308
    r=check(a,b)
    assert Fraction(r['counterexample']['difference_exact_mm'][2])==2*Fraction(1e308)


def test_same_geometric_segment_with_reversed_or_nonlinear_parameter_is_not_same_parameter_curve():
    a=line();b=line();b.across.c=b.across.c[::-1].copy()
    assert not check(a,b)['same_parameter_curve_exact_model']
    b=line(2);b.across.c[1,:,1]=0  # y=3s^2 spans the same segment.
    assert not check(a,b)['same_parameter_curve_exact_model']


def test_selected_span_range_ignores_difference_outside_that_range():
    along=BSpline([0,0,1,1],np.zeros((3,2,3)),1,axis=1)
    net=np.array([[[0,0,0],[1,0,0]],[[0,1,0],[1,1,0]],[[0,3,0],[1,3,0]]],float)
    a=SplineSurface(along,BSpline([0,0,.5,1,1],np.moveaxis(net,0,1),1,axis=1));b=deepcopy(a)
    b.across.c[-1,:,2]=1
    assert check(a,b,span_range=(0,.5))['same_parameter_curve_exact_model']
    assert not check(a,b)['same_parameter_curve_exact_model']


def test_c0_curves_are_compared_without_smoothing_or_resampling():
    a=line();a.across=a.across.insert_knot(.5);a.across.c[1,:,2]=1
    b=deepcopy(a);b.across=b.across.insert_knot(.25)
    assert check(a,b)['same_parameter_curve_exact_model']


def test_resource_limits_never_infer_identity_from_partial_work():
    a=line(3)
    for options,reason in [({'max_evaluations':1},'max_evaluations'),({'max_control_points':1},'max_control_points'),
                           ({'max_fraction_bits':1},'max_fraction_bits')]:
        r=check(a,a,**options)
        assert r['status']=='RESOURCE_LIMIT' and r['reason']==reason
        assert r['same_parameter_curve_exact_model'] is None and not r['identity_decided']


def test_fraction_limit_after_completed_evaluations_cannot_return_partial_equality():
    a=line(3);r=check(a,a,max_fraction_bits=3)
    assert r['status']=='RESOURCE_LIMIT' and r['checked_evaluations']>=2
    assert r['checked_intervals']==0 and r['same_parameter_curve_exact_model'] is None


def test_float_rounded_inserted_pole_is_not_exact_parameter_identity():
    a=line();net=np.zeros((3,2,3));net[:,:,0]=[0,1]
    net[:,:,1]=np.array([0,3*.1,3])[:,None]
    b=SplineSurface(a.along,BSpline([0,0,.1,1,1],np.moveaxis(net,0,1),1,axis=1))
    r=check(a,b)
    assert Fraction(r['counterexample']['span'])==Fraction(.1)
    assert Fraction(r['counterexample']['difference_exact_mm'][1])==Fraction(-1,2**55)
    # Both point sets still lie on the same straight segment; this is not a
    # nearest-distance or physical-gap assertion.
    assert not r['physical_gap_certified']


@pytest.mark.parametrize('options',[{'max_evaluations':False},{'max_control_points':0},{'max_fraction_bits':True},
    {'span_range':(1,0)},{'span_range':(False,True)},{'span_range':(-1,1)}])
def test_invalid_options(options):
    with pytest.raises(ValueError):check(line(),line(),**options)


@pytest.mark.parametrize('end',[True,1,-2])
def test_invalid_ends_are_rejected(end):
    with pytest.raises(ValueError):boundary_curve_identity(line(),end,line(),0)


def test_valid_end_selection_preserves_coordinate_identity():
    a=line();b=line();b.across.c=b.across.c[:,::-1].copy()
    assert boundary_curve_identity(a,0,b,-1)['same_parameter_curve_exact_model']
    assert not boundary_curve_identity(a,0,a,-1)['same_parameter_curve_exact_model']


def test_nonfinite_and_discontinuous_curves_are_rejected():
    a=line();a.across.c[0,0,0]=np.nan
    with pytest.raises(ValueError):check(a,line())
    a=line();a.across=a.across.insert_knot(.5,2)
    with pytest.raises(ValueError,match='Discontinuous'):check(a,a)


def test_all_role_seams_and_incomplete_aggregate_keep_source_and_status_contracts():
    source,_=fixture();before={r:s.across.c.copy() for r,s in source.items()}
    r=role_boundary_curve_identity(source)
    assert r['all_seams_identical_exact_model'] and r['scan_complete'] and len(r['seams'])==4
    limited=role_boundary_curve_identity(source,max_evaluations=1)
    assert limited['status']=='RESOURCE_LIMIT' and limited['all_seams_identical_exact_model'] is None
    source['ps'].across.c[:,:,2]+=1e-15
    mixed=role_boundary_curve_identity(source,max_fraction_bits=128)
    assert not mixed['all_seams_identical_exact_model']
    for role,s in source.items():
        if role!='ps':np.testing.assert_array_equal(s.across.c,before[role])
    with pytest.raises(ValueError):role_boundary_curve_identity({'le':source['le']})


def test_known_difference_and_other_undecided_seams_do_not_claim_complete_scan():
    source,_=fixture();source['ps'].across.c[:,:,2]+=1e-15
    source['te'].across.c[0,0,2]=np.nextafter(0.,1.)
    r=role_boundary_curve_identity(source,max_fraction_bits=128)
    assert r['status']=='EXACT_PARAMETER_CURVE_DIFFERENCE'
    assert r['all_seams_identical_exact_model'] is False and not r['scan_complete']
    assert any(s['report']['status']=='RESOURCE_LIMIT' for s in r['seams'])


@pytest.mark.parametrize('value',[Fraction(0),Fraction(-3),Fraction(2**16000+1,2**15999+1),
                                  Fraction(-(2**16000+1),2**15999+1)])
def test_bounded_large_rational_witness_format_does_not_change_global_digit_limit(value):
    original_limit=sys.get_int_max_str_digits()
    _Arithmetic(16384).check(value)
    text=_fraction_text(value);parts=text.split('/')
    decoded=Fraction(Decimal(parts[0]))/(Fraction(Decimal(parts[1])) if len(parts)>1 else 1)
    assert decoded==value and json.loads(json.dumps({'witness':text}))['witness']==text
    assert sys.get_int_max_str_digits()==original_limit
