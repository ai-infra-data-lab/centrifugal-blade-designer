"""Independent angular references and unsampled oriented-normal reversal."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import BSpline
from blade_designer.geometry.surface_evaluation import fit_surface_spline, SplineSurface
from blade_designer.geometry.surface_orientation import surface_normal_envelope


def patch(function, density=4, spans=(0.,.2,.7,1.)):
    t=np.linspace(0,1,density)
    return fit_surface_spline([function(s,t) for s in spans],density,spans=spans)


def plane(s,t):
    return np.column_stack((t,np.full(len(t),s),0*t))


@pytest.mark.parametrize('angle',[0.,25.,60.,90.,120.,180.])
def test_oriented_planar_angles_are_bounded_without_taking_absolute_dot(angle):
    rad=np.radians(angle)
    a=patch(plane)
    b=patch(lambda s,t:np.column_stack((t,np.full(len(t),s*np.cos(rad)),np.full(len(t),s*np.sin(rad)))))
    result=surface_normal_envelope(a,b,singular_mm2=1e-12)
    assert result['unresolved_cells']==0
    assert result['sample_max_degrees']==pytest.approx(angle,abs=2e-12)
    assert angle-2e-12 <= result['angle_upper_degrees'] <= 180.
    if angle<90:assert result['angle_upper_degrees']==pytest.approx(angle,abs=2e-12)
    assert result['roundoff_certified'] is False


@pytest.mark.parametrize('scale',[.01,1.,100.])
def test_positive_scale_and_different_knots_preserve_normal_and_inputs(scale):
    a=patch(plane,7,(0.,.1,.4,.8,1.))
    b=patch(lambda s,t:scale*plane(s,t),9)
    before=deepcopy([(s.along.t,s.along.c,s.across.t,s.across.c) for s in (a,b)])
    result=surface_normal_envelope(a,b,singular_mm2=1e-12,refinements=1)
    assert result['angle_upper_degrees']<1e-8
    for old,s in zip(before,(a,b)):
        for x,y in zip(old,(s.along.t,s.along.c,s.across.t,s.across.c)):np.testing.assert_array_equal(x,y)


def test_interior_reversed_hemisphere_is_not_hidden_by_nine_good_samples():
    a=patch(plane)
    b=patch(lambda s,t:np.column_stack((t,np.full(len(t),(s-.37)**3/3-.005*s),np.full(len(t),.01*s))))
    result=surface_normal_envelope(a,b,singular_mm2=1e-12)
    assert result['cell_count']==1 and result['unresolved_cells']==0
    assert result['sample_max_degrees']<90
    assert result['angle_upper_degrees']==180
    refined=surface_normal_envelope(a,b,singular_mm2=1e-12,refinements=4)
    assert refined['sample_max_degrees']>90
    for cell in refined['cells']:
        s=np.linspace(*cell['span_range'],23)
        exact=np.degrees(np.arctan2(.01,(s-.37)**2-.005))
        assert exact.max() <= cell['angle_upper_degrees']+2e-10
        assert cell['first_lower_mm2']>0 and cell['second_lower_mm2']>0


@pytest.mark.parametrize('fold',[False,True])
def test_undefined_or_unsampled_singular_normal_has_no_global_angle_bound(fold):
    a=patch(plane)
    b=patch(lambda s,t:np.column_stack((t,np.full(len(t),(s-.37)**2 if fold else 0),0*t)))
    result=surface_normal_envelope(a,b,singular_mm2=1e-12)
    assert result['angle_upper_degrees'] is None and result['unresolved_cells']>0
    if fold:
        assert result['sample_undefined_pairs']==0
        assert result['sample_max_degrees']==pytest.approx(180)
    else:
        assert result['sample_undefined_pairs']==9 and result['sample_max_degrees'] is None


def test_swapping_corresponding_surfaces_preserves_cell_bounds():
    a=patch(plane)
    b=patch(lambda s,t:np.column_stack((t,t**3+s**3,np.full(len(t),s))))
    first=surface_normal_envelope(a,b,singular_mm2=1e-12,refinements=1)
    second=surface_normal_envelope(b,a,singular_mm2=1e-12,refinements=1)
    for x,y in zip(first['cells'],second['cells']):
        assert x['angle_upper_degrees']==pytest.approx(y['angle_upper_degrees'],abs=1e-12)
        s=np.linspace(*x['span_range'],17)[:,None];t=np.linspace(*x['xi_range'],19)[None,:]
        # N_a=(0,0,-1); N_b=(-3t²,1,-3s²) for this analytic cubic.
        exact=np.degrees(np.arctan2(np.sqrt(9*t**4+np.ones_like(s)), 3*s**2))
        assert exact.max() <= x['angle_upper_degrees']+1e-11


@pytest.mark.parametrize('threshold',[-1,np.nan,np.inf,True,[1]])
def test_bad_threshold_is_not_silently_replaced(threshold):
    a=patch(plane)
    with pytest.raises(ValueError,match='singular_mm2'):surface_normal_envelope(a,a,singular_mm2=threshold)


@pytest.mark.parametrize('options',[{'refinements':-1},{'refinements':5},{'refinements':True},
                                    {'max_cells':0},{'max_cells':True},{'refinements':2,'max_cells':3}])
def test_bad_or_excessive_resources_are_rejected(options):
    a=patch(plane)
    with pytest.raises(ValueError):surface_normal_envelope(a,a,singular_mm2=0,**options)


def test_original_c0_seams_and_incompatible_degree_are_not_smoothed():
    a=patch(plane)
    c0=SplineSurface(BSpline([0,0,.5,1,1],np.zeros((2,3,3)),1,axis=1),
                     BSpline([0,0,1,1],np.zeros((3,2,3)),1,axis=1))
    # Matching C0 input is rejected before any derivative comparison.
    with pytest.raises(ValueError,match='C1'):surface_normal_envelope(c0,c0,singular_mm2=0)
    with pytest.raises(ValueError,match='degrees'):surface_normal_envelope(a,c0,singular_mm2=0)
