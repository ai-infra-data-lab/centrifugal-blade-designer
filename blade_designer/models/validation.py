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


def validate_impeller_trim(settings):
    from .parameters import ImpellerTrimParameters
    if settings is None:return
    if not isinstance(settings,ImpellerTrimParameters):raise ValueError('Invalid impeller trim settings.')
    values=[settings.shroud_area_cut_percent,settings.diameter_mm,settings.diameter_cut_percent]
    if any(not is_finite_number(x) for x in values):
        raise ValueError('Impeller trim values must be finite numbers.')
    if not 0<=settings.shroud_area_cut_percent<100 or not 0<=settings.diameter_cut_percent<100:
        raise ValueError('Impeller trim cut percentages must be in [0, 100).')
    if settings.diameter_mode not in ('off','diameter','percent') or settings.diameter_mm<0:
        raise ValueError('Invalid impeller trim diameter mode/value.')
    if settings.diameter_mode=='diameter' and settings.diameter_mm<=0:
        raise ValueError('Impeller trim diameter must be positive.')



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
    """Preserve the complete legacy radial-2D/project validation contract."""
    return _validate_settings(params, source="legacy")


def validate_row_settings(params: BladeParameters, kind: str) -> list[ValidationIssue]:
    """Validate 3D row settings; the generator validates actual sections/walls.

    Legacy radial extents and Hub aliases are not inputs to stator geometry.
    No values are repaired or substituted. Export precision remains a shared
    settings constraint, independent of the chosen geometry engine.
    """
    if kind not in ("impeller", "diffuser"):
        raise ValueError("Unknown 3D blade row kind.")
    return _validate_settings(params, source=kind)


def validate_stored_settings(params: BladeParameters) -> list[ValidationIssue]:
    """Typed value constraints for multi-row storage, without a radial flow assumption.

    Both legacy radii remain finite and positive, but their relative order is
    a legacy geometry constraint checked only when that engine is requested.
    """
    return _validate_settings(params, source="stored")


def _validate_settings(params: BladeParameters, *, source: str) -> list[ValidationIssue]:
    issues = []
    def error(field: str, message: str) -> None:
        issues.append(ValidationIssue(ValidationLevel.ERROR, field, message))
    from .parameters import RotationDirection
    if not isinstance(params.rotation_direction, RotationDirection):
        error("rotation_direction", "Unknown rotation direction.")
    g = params.geometry
    for name in (("r_le", "r_te", "theta_le_deg") if source in ("legacy", "stored") else ("theta_le_deg",)):
        if not is_finite_number(getattr(g, name)):
            error(name, "Must be a finite number.")
    if source == "legacy" and not issues:
        if g.r_le <= 0:
            error("r_le", "R LE must be > 0.")
        if g.r_te <= g.r_le:
            error("r_te", "R TE must be > R LE.")
    if source == "stored":
        for name in ("r_le", "r_te"):
            if is_finite_number(getattr(g, name)) and getattr(g, name) <= 0:
                error(name, "Stored radius must be > 0.")
    if isinstance(g.vane_count, bool) or not isinstance(g.vane_count, Integral) or g.vane_count < 1:
        error("vane_count", "Vane count must be an integer >= 1.")
    if source in ("legacy", "stored"):
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
    if source == "diffuser":
        return issues
    rake=params.impeller_te_rake_deg
    if rake is not None and (not is_finite_number(rake) or not -90<rake<90):
        error("impeller_te_rake_deg", "TE Rake must be finite and strictly between -90 and 90 degrees.")
    try:validate_impeller_trim(params.impeller_trim)
    except ValueError as exc:error('impeller_trim',str(exc))
    from .parameters import TipClearanceParameters
    clearance=params.tip_clearance
    if clearance is not None:
        if not isinstance(clearance,TipClearanceParameters):
            error("tip_clearance", "Invalid Tip clearance parameters.")
        elif any(not is_finite_number(v) or v<0 for v in (clearance.le_mm,clearance.te_mm)):
            error("tip_clearance", "Tip clearance LE/TE must be finite and >= 0 mm.")
    from .parameters import SplitterParameters
    splitter=params.splitter
    if splitter is not None:
        if not isinstance(splitter,SplitterParameters):
            error("splitter", "Invalid splitter parameters.")
        else:
            for name in ("hub_start_fraction","tip_start_fraction","pitch_fraction"):
                value=getattr(splitter,name)
                if not is_finite_number(value) or not 0<value<1:
                    error("splitter."+name, "Splitter fractions must be finite and strictly between 0 and 1.")
            if splitter.sections is not None:
                profiles=splitter.sections
                from .parameters import BladeSection
                if not isinstance(profiles,list) or len(profiles)<2 or any(not isinstance(s,BladeSection) or not is_finite_number(s.span) for s in profiles):
                    error("splitter.sections", "Splitter requires valid Hub/Tip profiles.")
                else:
                    spans=[s.span for s in profiles]
                    if spans[0]!=0 or spans[-1]!=1 or any(b<=a for a,b in zip(spans,spans[1:])):
                        error("splitter.sections", "Splitter spans must increase from Hub 0 to Tip 1.")
                    for s in profiles:
                        issues.extend(validate_control_points(s.blade_angle.points,"blade_angle"))
                        issues.extend(validate_control_points(s.thickness.points,"thickness"))
            if not is_finite_number(splitter.thickness_scale) or splitter.thickness_scale<=0:
                error("splitter.thickness_scale", "Splitter thickness scale must be finite and > 0.")
    return issues
