from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters, DistributionPoint
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.optimization.parameter_mapper import ParameterMapper
from blade_designer.optimization.presets import default_parameters
from blade_designer.optimization.models import GeometryConstraints
from blade_designer.optimization.feasibility import evaluate_candidate,check_feasibility,maximum_angle_derivatives,angle_derivatives


def test_baseline_accepts_le_throat(default_blade):
    assert "LE" in (default_blade.metrics.throat.blade1_segment,default_blade.metrics.throat.blade2_segment)
    assert not any("Throat lies on edge" in i.message for i in default_blade.warnings)
    assert check_feasibility(BladeParameters(),default_blade,GeometryConstraints()).feasible


@pytest.mark.parametrize("name,value", [
    ("minimum_thickness",2.),("maximum_curvature",.00001),("minimum_curvature_radius",10000.),
    ("minimum_throat",100.),("maximum_throat",1.),("minimum_te_thickness",2.),
    ("maximum_turning_gradient",.1),("maximum_turning_second_derivative",.1),
])
def test_individual_constraints(default_blade,name,value):
    constraints = GeometryConstraints()
    setattr(constraints,name,value)
    result = check_feasibility(BladeParameters(),default_blade,constraints)
    assert not result.feasible
    assert any(not c.passed for c in result.checks)


def test_analytic_gradient_between_samples():
    b = BladeParameters()
    b.blade_angle.points = [DistributionPoint(0,0),DistributionPoint(.49999,0),
                           DistributionPoint(.50001,1),DistributionPoint(1,1)]
    gradient,second = maximum_angle_derivatives(b)
    assert gradient == pytest.approx(75000.,rel=1e-7)
    assert second > 1e9
    d1,d2 = angle_derivatives(b,np.array([.5]))
    assert d1[0] == pytest.approx(gradient)


def test_rejected_candidate_and_invalid_vector_results():
    b = BladeParameters()
    mapper = ParameterMapper(default_parameters(b),b)
    result = evaluate_candidate(mapper,mapper.initial_vector(),GeometryConstraints(minimum_throat=100.))
    assert not result.feasible
    failed = [check for check in result.feasibility.checks if not check.passed]
    assert [check.name for check in failed] == ["Minimum throat [mm]"]
    assert result.geometry is not None
    invalid = evaluate_candidate(mapper,[-1]*len(mapper.active_parameters))
    assert not invalid.feasible and invalid.geometry is None


def test_single_blade_constraints_are_explicit():
    b = BladeParameters()
    b.geometry.vane_count = 1
    mapper = ParameterMapper(default_parameters(b),b)
    assert not evaluate_candidate(mapper,mapper.initial_vector()).feasible
    constraints = GeometryConstraints(minimum_throat=None,maximum_throat=None)
    assert evaluate_candidate(mapper,mapper.initial_vector(),constraints).feasible
