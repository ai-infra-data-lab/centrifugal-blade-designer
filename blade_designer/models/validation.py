from dataclasses import dataclass
from enum import Enum
from numbers import Real, Integral
import math
from .parameters import BladeParameters, DistributionPoint, EdgeType, SurfaceMapping


class ValidationLevel(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationIssue:
    level: ValidationLevel
    field: str
    message: str


def is_finite_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def validate_control_points(points: list[DistributionPoint], kind: str) -> list[ValidationIssue]:
    issues = []
    def error(message: str) -> None:
        issues.append(ValidationIssue(ValidationLevel.ERROR, kind, message))
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        error("At least two control points are required.")
        return issues
    if not all(isinstance(p, DistributionPoint) and is_finite_number(p.m_norm)
               and is_finite_number(p.value) for p in points):
        error("Control points must contain finite numeric positions and values.")
        return issues
    if points[0].m_norm != 0 or points[-1].m_norm != 1:
        error("Endpoints at Normalized Meridional = 0 and 1 are required.")
    if any(not 0 <= p.m_norm <= 1 for p in points) or any(b.m_norm <= a.m_norm for a, b in zip(points, points[1:])):
        error("Normalized Meridional must increase strictly from 0 to 1; duplicates are forbidden.")
    if kind == "blade_angle":
        if any(abs(p.value) >= 85 for p in points):
            error("All blade angles must satisfy -85 < βm < 85 deg.")
        elif any(abs(p.value) > 80 for p in points):
            issues.append(ValidationIssue(ValidationLevel.WARNING, kind, "|βm| > 80 deg."))
    elif any(p.value < 0 for p in points):
        error("Thickness must be >= 0.")
    return issues


def validate_parameters(params: BladeParameters) -> list[ValidationIssue]:
    issues = []
    def error(field: str, message: str) -> None:
        issues.append(ValidationIssue(ValidationLevel.ERROR, field, message))
    from .parameters import RotationDirection
    if not isinstance(params.rotation_direction, RotationDirection):
        error("rotation_direction", "Unknown rotation direction.")
    g = params.geometry
    for name in ("r_le", "r_te", "theta_le_deg"):
        if not is_finite_number(getattr(g, name)):
            error(name, "Must be a finite number.")
    if not issues:
        if g.r_le <= 0:
            error("r_le", "R LE must be > 0.")
        if g.r_te <= g.r_le:
            error("r_te", "R TE must be > R LE.")
    if isinstance(g.vane_count, bool) or not isinstance(g.vane_count, Integral) or g.vane_count < 1:
        error("vane_count", "Vane count must be an integer >= 1.")
    issues.extend(validate_control_points(params.blade_angle.points, "blade_angle"))
    issues.extend(validate_control_points(params.thickness.points, "thickness"))
    for name in ("le_type", "te_type"):
        if not isinstance(getattr(params.edges, name), EdgeType):
            error(name, "Unknown edge type.")
    for name in ("le_ellipse_ratio", "te_ellipse_ratio"):
        value = getattr(params.edges, name)
        if not is_finite_number(value) or value <= 0:
            error(name, "Ellipse ratio must be finite and > 0.")
    for name, value in vars(params.output_points).items():
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 2:
            error(name, "Each segment requires an integer point count >= 2.")
    d = params.export.significant_digits
    if isinstance(d, bool) or not isinstance(d, Integral) or not 1 <= d <= 15:
        error("significant_digits", "Significant digits must be an integer from 1 to 15.")
    if not isinstance(params.export.repeat_first_point, bool):
        error("repeat_first_point", "Must be a boolean.")
    if not isinstance(params.surface_mapping, SurfaceMapping):
        error("surface_mapping", "Unknown surface mapping.")
    return issues
