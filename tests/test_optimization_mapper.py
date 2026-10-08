from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters, EdgeType
from blade_designer.optimization.models import (OptimizationVariables, ValueMode, OptimizationMode,
    OptimizationParameter, ParameterType)
from blade_designer.optimization.parameter_mapper import ParameterMapper, optimization_to_design
from blade_designer.optimization.presets import default_parameters
from blade_designer.geometry.distributions import interpolate_beta_m_deg


def test_initial_neutral_and_immutable():
    baseline = BladeParameters()
    saved = deepcopy(baseline)
    parameters = default_parameters(baseline)
    assert len(parameters) == 9
    assert len(default_parameters(baseline,compact=True)) == 7
    mapper = ParameterMapper(parameters,baseline)
    candidate = mapper.create_design(mapper.initial_vector())
    assert candidate == baseline
    candidate.blade_angle.points[0].value = 10
    baseline.geometry.r_le = 110
    assert mapper.baseline == saved
    parameters[0].initial = 3
    assert mapper.parameters[0].initial == 0


def test_bow_endpoints_and_midpoint():
    b = BladeParameters()
    d = optimization_to_design(OptimizationVariables({"beta_bow":3.}),b)
    assert d.blade_angle.points[0] == b.blade_angle.points[0]
    assert d.blade_angle.points[-1] == b.blade_angle.points[-1]
    values = interpolate_beta_m_deg(np.array([.5]),d.blade_angle.points)
    assert values[0] == pytest.approx(61.)


def test_absolute_and_delta():
    b = BladeParameters()
    a = optimization_to_design(OptimizationVariables({"beta_te":48.}),b)
    d = optimization_to_design(OptimizationVariables({"beta_te":-2.},{"beta_te":ValueMode.DELTA}),b)
    assert a == d
    assert a.blade_angle.points[-1].value == 48.


def test_scale_shift_and_endpoint_override():
    b = BladeParameters()
    scale = optimization_to_design(OptimizationVariables({"thickness_scale":1.2}),b)
    np.testing.assert_allclose([p.value for p in scale.thickness.points],[1.2,4.8,1.2])
    shift = optimization_to_design(OptimizationVariables({"m_tmax_shift":.1},{"m_tmax_shift":ValueMode.DELTA}),b)
    assert shift.thickness.points[1].m_norm == pytest.approx(.45)
    np.testing.assert_allclose([p.value for p in shift.thickness.points],[1,4,1])
    d = optimization_to_design(OptimizationVariables({"thickness_scale":1.2,"te_thickness":.7}),b)
    assert d.thickness.points[0].value == pytest.approx(1.2)
    assert d.thickness.points[-1].value == .7


def test_local_modifiers_fixed_topology():
    b = BladeParameters()
    d = optimization_to_design(OptimizationVariables({"thickness_front":.2,"thickness_rear":-.1}),b)
    assert d.geometry == b.geometry and d.edges == b.edges
    assert d.thickness.points[0].value == 1 and d.thickness.points[-1].value == 1
    with pytest.raises(ValueError):
        optimization_to_design(OptimizationVariables({"thickness_front":-2}),b)


def test_geometry_vs_architecture():
    b = BladeParameters()
    with pytest.raises(ValueError):
        optimization_to_design(OptimizationVariables({"r_le":105}),b)
    d = optimization_to_design(OptimizationVariables({"r_le":105,"vane_count":19},
                              optimization_mode=OptimizationMode.ARCHITECTURE),b)
    assert d.geometry.r_le == 105 and d.geometry.vane_count == 19
    with pytest.raises(ValueError):
        optimization_to_design(OptimizationVariables({"vane_count":19.5},
                                optimization_mode=OptimizationMode.ARCHITECTURE),b)


def test_normalization_discrete_integer_and_disabled():
    b = BladeParameters()
    params = [
        OptimizationParameter("beta_bow",ParameterType.CONTINUOUS,-5,5,0,scale=2),
        OptimizationParameter("vane_count",ParameterType.DISCRETE,17,22,20,choices=(17,20,22)),
        OptimizationParameter("beta_offset",ParameterType.INTEGER,-2,2,0),
        OptimizationParameter("te_thickness",ParameterType.FIXED,1,1,1),
        OptimizationParameter("r_le",ParameterType.CONTINUOUS,90,110,105,enabled=False),
    ]
    mapper = ParameterMapper(params,b,OptimizationMode.ARCHITECTURE)
    np.testing.assert_allclose(mapper.initial_vector(),[.5,.5,.5])
    v = mapper.decode([1,.5,.75])
    assert v.values == {"beta_bow":5.,"vane_count":20,"beta_offset":1,"te_thickness":1}
    assert mapper.create_design([.5,.5,.5]).geometry.r_le == b.geometry.r_le
    assert mapper.decode([.5,1,.5]).values["vane_count"] == 22
    with pytest.raises(ValueError): mapper.decode([0,19,0],normalized=False)


@pytest.mark.parametrize("value",[-.1,1.1,float("nan"),True])
def test_invalid_normalized_vector(value):
    mapper = ParameterMapper([OptimizationParameter("beta_bow",ParameterType.CONTINUOUS,-5,5,0)],BladeParameters())
    with pytest.raises(ValueError): mapper.create_design([value])


def test_bad_configuration_and_no_effect_variable():
    b = BladeParameters()
    params = default_parameters(b)
    ratio = next(p for p in params if p.name == "le_ellipse_ratio")
    assert not ratio.enabled
    ratio.enabled = True
    with pytest.raises(ValueError): ParameterMapper(params,b)
    b.edges.le_type = EdgeType.ELLIPTICAL
    mapper = ParameterMapper(params,b)
    assert len(mapper.active_parameters) == 9
    with pytest.raises(ValueError):
        ParameterMapper([OptimizationParameter("vane_count",ParameterType.CONTINUOUS,17,22,20)],b,OptimizationMode.ARCHITECTURE)


def test_reject_invalid_candidate_mapping():
    with pytest.raises(ValueError):
        optimization_to_design(OptimizationVariables({"beta_bow":100}),BladeParameters())
    with pytest.raises(ValueError):
        optimization_to_design(OptimizationVariables({"m_tmax_shift":.9},{"m_tmax_shift":ValueMode.DELTA}),BladeParameters())
