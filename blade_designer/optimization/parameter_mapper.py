"""Mapping never mutates its baseline and never imports a GUI or optimizer."""
from copy import deepcopy
from numbers import Real
from collections.abc import Sequence
import numpy as np
from ..geometry.distributions import distribution_interpolator
from ..models.parameters import BladeParameters, DistributionPoint, EdgeType
from ..models.validation import validate_parameters, ValidationLevel, is_finite_number
from ..geometry.thickness import thickness_interpolator
from .models import OptimizationVariables, OptimizationParameter, ParameterType, ValueMode, OptimizationMode

ANGLE_POSITIONS = {"beta_le":0., "beta_25":.25, "beta_30":.3, "beta_50":.5,
                   "beta_60":.6, "beta_75":.75, "beta_te":1.}
SUPPORTED_NAMES = set(ANGLE_POSITIONS) | {"beta_bow", "beta_offset", "thickness_scale", "m_tmax_shift",
    "thickness_front", "thickness_rear", "le_thickness", "te_thickness",
    "le_ellipse_ratio", "te_ellipse_ratio", "r_le", "r_te", "vane_count"}
ARCHITECTURE_NAMES = {"r_le", "r_te", "vane_count"}


def _design_grid(anchors: Sequence[float]) -> np.ndarray:
    anchors = np.unique(np.asarray(anchors,dtype=float))
    regular = np.linspace(0.,1.,101)
    # Keep exact source positions; do not create a second knot a few ULPs away.
    keep = np.min(np.abs(regular[:,None]-anchors[None,:]),axis=1) > 1e-12
    return np.sort(np.r_[regular[keep],anchors])


def _validate_design(params: BladeParameters) -> None:
    errors = [i for i in validate_parameters(params) if i.level == ValidationLevel.ERROR]
    if errors:
        raise ValueError("; ".join(f"{i.field}: {i.message}" for i in errors))


def _peak_position(baseline: BladeParameters) -> float:
    points = baseline.thickness.points
    # First maximum for a plateau; documented deterministic definition.
    return float(max(points, key=lambda p:p.value).m_norm)


def optimization_to_design(variables: OptimizationVariables, baseline: BladeParameters) -> BladeParameters:
    _validate_design(baseline)
    if not isinstance(variables.optimization_mode, OptimizationMode):
        raise ValueError("Unknown optimization mode.")
    values = variables.values
    if not set(values) <= SUPPORTED_NAMES:
        raise ValueError(f"Unsupported variables: {sorted(set(values)-SUPPORTED_NAMES)}")
    if not set(variables.value_modes) <= set(values):
        raise ValueError("A value mode was supplied without a variable.")
    if any(not is_finite_number(v) for v in values.values()):
        raise ValueError("All optimization values must be finite physical numbers.")
    if any(not isinstance(v,ValueMode) for v in variables.value_modes.values()):
        raise ValueError("Unknown Absolute/Delta mode.")
    if variables.optimization_mode == OptimizationMode.GEOMETRY and set(values) & ARCHITECTURE_NAMES:
        raise ValueError("R LE, R TE and Vane Count are fixed in Geometry Optimization.")
    candidate = deepcopy(baseline)
    def physical(name: str, base: float) -> float:
        if name not in values:
            return base
        value = float(values[name])
        return base+value if variables.value_modes.get(name,ValueMode.ABSOLUTE) == ValueMode.DELTA else value

    angle_points = baseline.blade_angle.points
    angle = distribution_interpolator([p.m_norm for p in angle_points],[p.value for p in angle_points])
    knots = {0.:0.,1.:0.}
    for name,m in ANGLE_POSITIONS.items():
        if name in values:
            base = float(angle(m))
            knots[m] = physical(name,base)-base
    bow, offset = physical("beta_bow",0.), physical("beta_offset",0.)
    if any(v != 0 for v in knots.values()) or bow or offset:
        controls = np.array(sorted(knots))
        offsets = np.array([knots[m] for m in controls])
        m = _design_grid([p.m_norm for p in angle_points]+list(controls))
        beta = angle(m) + distribution_interpolator(controls,offsets)(m) + bow*4*m*(1-m) + offset
        candidate.blade_angle.points = [DistributionPoint(float(x),float(y)) for x,y in zip(m,beta)]

    scale = physical("thickness_scale",1.)
    if scale <= 0:
        raise ValueError("Thickness scale must be > 0.")
    peak = _peak_position(baseline)
    target_peak = physical("m_tmax_shift",peak)
    shifted = target_peak != peak
    if shifted and not (0 < peak < 1 and 0 < target_peak < 1):
        raise ValueError("Thickness peak shifting requires an interior baseline and target peak.")
    front, rear = physical("thickness_front",0.), physical("thickness_rear",0.)
    if min(front,rear) < -1:
        raise ValueError("Local thickness modifiers must be >= -1 to keep thickness nonnegative.")
    tp = baseline.thickness.points
    if front or rear:
        m = _design_grid([p.m_norm for p in tp]+[.25,.5,.75])
        t = thickness_interpolator(baseline.thickness)(m)
    else:
        m = np.array([p.m_norm for p in tp])
        t = np.array([p.value for p in tp],dtype=float)
    if shifted:
        m = np.where(m <= peak,m*target_peak/peak,
                     target_peak+(m-peak)*(1-target_peak)/(1-peak))
        m[0],m[-1] = 0.,1.
    f_front = np.where(m <= .5,np.sin(2*np.pi*m)**2,0.)
    f_rear = np.where(m >= .5,np.sin(2*np.pi*m)**2,0.)
    t = scale*t*(1+front*f_front+rear*f_rear)
    # Explicit endpoint values override the scaled endpoint; Delta is relative to baseline.
    t[0] = physical("le_thickness",tp[0].value) if "le_thickness" in values else t[0]
    t[-1] = physical("te_thickness",tp[-1].value) if "te_thickness" in values else t[-1]
    candidate.thickness.points = [DistributionPoint(float(x),float(y)) for x,y in zip(m,t)]
    for side in ("le","te"):
        name = side+"_ellipse_ratio"
        if name in values and getattr(baseline.edges,side+"_type") != EdgeType.ELLIPTICAL:
            raise ValueError(f"{name} requires an Elliptical baseline edge. Edge types remain fixed.")
        setattr(candidate.edges,name,physical(name,getattr(baseline.edges,name)))
    for name in ("r_le","r_te"):
        setattr(candidate.geometry,name,physical(name,getattr(baseline.geometry,name)))
    count = physical("vane_count",baseline.geometry.vane_count)
    if count != int(count):
        raise ValueError("Vane Count must be an integer; continuous rounding is not allowed.")
    candidate.geometry.vane_count = int(count)
    _validate_design(candidate)
    return candidate


class ParameterMapper:
    def __init__(self, parameters: Sequence[OptimizationParameter], baseline: BladeParameters,
                 mode: OptimizationMode = OptimizationMode.GEOMETRY) -> None:
        self._parameters = deepcopy(list(parameters))
        self._baseline = deepcopy(baseline)
        self.mode = mode
        self._validate()

    @property
    def parameters(self) -> list[OptimizationParameter]:
        return deepcopy(self._parameters)

    @property
    def baseline(self) -> BladeParameters:
        return deepcopy(self._baseline)

    @property
    def active_parameters(self) -> list[OptimizationParameter]:
        return deepcopy([p for p in self._parameters if p.enabled and p.parameter_type != ParameterType.FIXED])

    def _validate(self) -> None:
        _validate_design(self._baseline)
        if not isinstance(self.mode,OptimizationMode):
            raise ValueError("Unknown optimization mode.")
        if len({p.name for p in self._parameters}) != len(self._parameters):
            raise ValueError("Optimization parameter names must be unique.")
        for p in self._parameters:
            if p.name not in SUPPORTED_NAMES:
                raise ValueError(f"Unknown optimization parameter: {p.name}")
            if not isinstance(p.parameter_type,ParameterType) or not isinstance(p.value_mode,ValueMode):
                raise ValueError(f"{p.name}: invalid type or value mode.")
            if not isinstance(p.enabled,bool):
                raise ValueError(f"{p.name}: enabled must be a boolean.")
            if not all(is_finite_number(x) for x in (p.lower,p.upper,p.initial,p.scale)) or p.scale <= 0:
                raise ValueError(f"{p.name}: bounds, initial and positive scale must be finite.")
            if not p.lower <= p.initial <= p.upper:
                raise ValueError(f"{p.name}: lower <= initial <= upper is required.")
            if p.enabled and p.parameter_type != ParameterType.FIXED and p.lower == p.upper:
                raise ValueError(f"{p.name}: variable bounds must differ; use Fixed for a constant.")
            if p.parameter_type == ParameterType.INTEGER and any(float(v) != int(v) for v in (p.lower,p.upper,p.initial)):
                raise ValueError(f"{p.name}: integer bounds and initial required.")
            if p.parameter_type == ParameterType.DISCRETE:
                if not p.choices or any(not is_finite_number(x) for x in p.choices):
                    raise ValueError(f"{p.name}: discrete choices must be finite numbers.")
                if tuple(sorted(set(p.choices))) != tuple(p.choices) or p.initial not in p.choices:
                    raise ValueError(f"{p.name}: choices must be unique, sorted and contain initial.")
                if min(p.choices)<p.lower or max(p.choices)>p.upper:
                    raise ValueError(f"{p.name}: all choices must lie inside bounds.")
            if p.name == "vane_count":
                if p.parameter_type == ParameterType.CONTINUOUS:
                    raise ValueError("Vane Count cannot be a continuous parameter.")
                if any(float(v) != int(v) for v in (p.initial,*p.choices)):
                    raise ValueError("Vane Count values must be integers.")
            if p.enabled and self.mode == OptimizationMode.GEOMETRY and p.name in ARCHITECTURE_NAMES:
                raise ValueError(f"{p.name} requires Architecture Optimization.")
            if p.enabled and p.name in ("le_ellipse_ratio","te_ellipse_ratio"):
                if getattr(self._baseline.edges,p.name[:2]+"_type") != EdgeType.ELLIPTICAL:
                    raise ValueError(f"{p.name}: capture an Elliptical baseline or disable this variable.")

    def initial_vector(self, normalized: bool = True) -> np.ndarray:
        values = np.array([p.initial for p in self.active_parameters],dtype=float)
        return self.normalize(values) if normalized else values

    def normalize(self, physical_vector: Sequence[float]) -> np.ndarray:
        values = self._check_vector(physical_vector,normalized=False)
        result = []
        for p,value in zip(self.active_parameters,values):
            self._check_physical(p,value)
            result.append(p.choices.index(value)/(len(p.choices)-1) if p.parameter_type == ParameterType.DISCRETE and len(p.choices)>1
                          else 0. if p.parameter_type == ParameterType.DISCRETE else (value-p.lower)/(p.upper-p.lower))
        return np.asarray(result,dtype=float)

    def _check_vector(self, vector: Sequence[float], normalized: bool) -> np.ndarray:
        if any(not is_finite_number(x) for x in vector):
            raise ValueError("Vector entries must be finite numbers.")
        values = np.asarray(vector,dtype=float)
        if values.ndim != 1 or len(values) != len(self.active_parameters):
            raise ValueError(f"Expected {len(self.active_parameters)} active vector values.")
        if normalized and (np.any(values<0) or np.any(values>1)):
            raise ValueError("Normalized values must lie in [0, 1].")
        return values

    def _check_physical(self, p: OptimizationParameter, value: float) -> None:
        if not p.lower <= value <= p.upper:
            raise ValueError(f"{p.name}: value outside configured bounds.")
        if p.parameter_type == ParameterType.INTEGER and value != int(value):
            raise ValueError(f"{p.name}: value must be an integer.")
        if p.parameter_type == ParameterType.DISCRETE and value not in p.choices:
            raise ValueError(f"{p.name}: value must be one of {p.choices}.")

    def decode(self, vector: Sequence[float], normalized: bool = True) -> OptimizationVariables:
        numbers = self._check_vector(vector,normalized)
        variables = OptimizationVariables(optimization_mode=self.mode)
        for p,number in zip(self.active_parameters,numbers):
            value = float(number)
            if normalized:
                if p.parameter_type == ParameterType.DISCRETE:
                    value = p.choices[min(int(np.floor(number*(len(p.choices)-1)+.5)),len(p.choices)-1)]
                else:
                    value = p.lower+number*(p.upper-p.lower)
                    if p.parameter_type == ParameterType.INTEGER:
                        value = int(np.floor(value+.5))
            self._check_physical(p,value)
            variables.values[p.name] = value
            variables.value_modes[p.name] = p.value_mode
        for p in self._parameters:
            if p.enabled and p.parameter_type == ParameterType.FIXED:
                variables.values[p.name] = p.initial
                variables.value_modes[p.name] = p.value_mode
        return variables

    def create_design(self, vector: Sequence[float], normalized: bool = True) -> BladeParameters:
        return optimization_to_design(self.decode(vector,normalized),self._baseline)
