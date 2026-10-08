from dataclasses import dataclass, field
from enum import Enum
from ..models.parameters import BladeParameters
from ..models.geometry import BladeGeometry


class ParameterType(str, Enum):
    CONTINUOUS = "continuous"
    INTEGER = "integer"
    DISCRETE = "discrete"
    FIXED = "fixed"


class ValueMode(str, Enum):
    ABSOLUTE = "absolute"
    DELTA = "delta"


class OptimizationMode(str, Enum):
    GEOMETRY = "geometry"
    ARCHITECTURE = "architecture"


@dataclass
class OptimizationParameter:
    name: str
    parameter_type: ParameterType
    lower: float | int
    upper: float | int
    initial: float | int
    scale: float = 1.0
    enabled: bool = True
    value_mode: ValueMode = ValueMode.ABSOLUTE
    group: str = "Blade Angle"
    choices: tuple[float | int, ...] = ()


@dataclass
class OptimizationVariables:
    values: dict[str, float | int] = field(default_factory=dict)
    value_modes: dict[str, ValueMode] = field(default_factory=dict)
    optimization_mode: OptimizationMode = OptimizationMode.GEOMETRY


@dataclass
class GeometryConstraints:
    no_self_intersection: bool = True
    minimum_thickness: float | None = 0.1
    maximum_curvature: float | None = 1.0
    minimum_curvature_radius: float | None = 0.1
    minimum_throat: float | None = 0.0
    maximum_throat: float | None = None
    minimum_te_thickness: float | None = 0.1
    maximum_turning_gradient: float | None = 200.0
    maximum_turning_second_derivative: float | None = None


@dataclass
class ConstraintCheck:
    name: str
    passed: bool
    actual: float | bool | None
    limit: float | bool | None
    message: str = ""


@dataclass
class FeasibilityResult:
    checks: list[ConstraintCheck] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return all(check.passed for check in self.checks)


@dataclass
class CandidateResult:
    design: BladeParameters | None
    geometry: BladeGeometry | None
    feasibility: FeasibilityResult

    @property
    def feasible(self) -> bool:
        return self.design is not None and self.geometry is not None and self.feasibility.feasible
