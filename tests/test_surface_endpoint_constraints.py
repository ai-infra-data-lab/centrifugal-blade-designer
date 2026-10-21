"""Endpoint constraints are data, not tolerance-based seam repairs."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import make_interp_spline
from blade_designer.geometry.surface_evaluation import fit_surface_spline
from blade_designer.geometry.boundary_identity import boundary_curve_identity


@pytest.mark.parametrize('density',[2,3,4,17,65])
def test_endpoint_poles_are_input_data_for_unconstrained_degrees(density):
    t=np.linspace(0,1,density);rows=[np.column_stack((t+7.3,t**2+.17,np.full(len(t),s))) for s in (0.,.2,.7,1.)]
    model=fit_surface_spline(rows,density,spans=[0,.2,.7,1])
    np.testing.assert_array_equal(model.along.c[0],np.array(rows)[:,0])
    np.testing.assert_array_equal(model.along.c[-1],np.array(rows)[:,-1])
    np.testing.assert_allclose(model.along(t),np.array(rows),rtol=0,atol=1e-13)


@pytest.mark.parametrize('density',[4,17,65,129])
def test_clamped_cubic_preserves_data_tangents_and_legacy_mathematical_interpolant(density):
    spans=np.array([0.,.2,.7,1.]);t=np.linspace(0,1,density)
    rows=np.array([np.column_stack((t+7.3,t**3+.17+s**3,np.full(len(t),s))) for s in spans])
    tangents=np.array([[[1,0,0]]*4,[[1,3,0]]*4],dtype=float);before=deepcopy((rows,tangents))
    model=fit_surface_spline(rows,density,spans=spans,tangents=tangents)
    old=make_interp_spline(t,rows,k=3,axis=1,bc_type=([(1,tangents[0])],[(1,tangents[1])]))
    np.testing.assert_array_equal(model.along.t,old.t)
    assert model.along.k==old.k and model.along.axis==old.axis
    np.testing.assert_array_equal(model.along.c[0],rows[:,0])
    np.testing.assert_array_equal(model.along.c[-1],rows[:,-1])
    np.testing.assert_allclose(model.along(t),rows,rtol=0,atol=3e-14)
    for endpoint in (0,1):
        np.testing.assert_allclose(model.along.derivative()(endpoint),tangents[endpoint],rtol=0,atol=2e-12)
    query=np.linspace(0,1,127)
    np.testing.assert_allclose(model.along(query),old(query),rtol=0,atol=3e-14)
    x,y=np.meshgrid(query,spans)
    np.testing.assert_allclose(model.evaluate_grid(spans,query),np.stack((x+7.3,x**3+.17+y**3,y),axis=-1),rtol=0,atol=3e-14)
    np.testing.assert_array_equal(rows,before[0]);np.testing.assert_array_equal(tangents,before[1])


@pytest.mark.parametrize('densities',[(17,65),(33,129),(65,65)])
def test_shared_boundary_is_exact_even_with_different_interior_and_tangents(densities):
    spans=np.array([0.,.2,.7,1.]);models=[]
    for index,density in enumerate(densities):
        t=np.linspace(0,1,density)
        rows=np.array([np.column_stack((50.1+t*(index+1),.17+s**3+t**2*(index+1),np.full(len(t),s))) for s in spans])
        tangents=np.array([[[index+1,0,0]]*4,[[index+1,2*(index+1),0]]*4],dtype=float)
        models.append(fit_surface_spline(rows,density,spans=spans,tangents=tangents))
    np.testing.assert_array_equal(models[0].across.c[:,0],models[1].across.c[:,0])
    report=boundary_curve_identity(models[0],0,models[1],0)
    assert report['same_parameter_curve_exact_model'] is True


def test_real_input_endpoint_gap_is_preserved_and_not_welded():
    t=np.linspace(0,1,17);rows=[np.column_stack((10+t,.17+t*t,np.full(len(t),s))) for s in (0.,1.)]
    first=fit_surface_spline(rows,17)
    altered=deepcopy(rows)
    for row in altered:row[0,0]=np.nextafter(row[0,0],np.inf)
    second=fit_surface_spline(altered,17)
    assert boundary_curve_identity(first,0,second,0)['same_parameter_curve_exact_model'] is False
