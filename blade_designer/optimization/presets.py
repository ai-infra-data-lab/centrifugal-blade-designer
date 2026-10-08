from ..models.parameters import BladeParameters, EdgeType
from .models import OptimizationParameter, ParameterType, ValueMode, OptimizationMode

GROUPS = ("Blade Angle", "Thickness", "Leading Edge", "Trailing Edge", "Vane Arrangement", "Global Geometry")


def default_parameters(baseline: BladeParameters, compact: bool = False,
                       mode: OptimizationMode = OptimizationMode.GEOMETRY) -> list[OptimizationParameter]:
    result = []
    def add(name: str, lower: float, upper: float, initial: float, group: str,
            value_mode: ValueMode = ValueMode.ABSOLUTE, enabled: bool = True) -> None:
        result.append(OptimizationParameter(name, ParameterType.CONTINUOUS, lower, upper, initial,
                                            enabled=enabled, value_mode=value_mode, group=group))
    for name in (("beta_le", "beta_bow", "beta_te") if compact else
                 ("beta_le", "beta_25", "beta_50", "beta_75", "beta_te")):
        add(name, -5., 5., 0., "Blade Angle", ValueMode.DELTA)
    add("thickness_scale", .8, 1.2, 1., "Thickness")
    add("m_tmax_shift", -.1, .1, 0., "Thickness", ValueMode.DELTA)
    ratio = baseline.edges.le_ellipse_ratio
    add("le_ellipse_ratio", min(.7, ratio), max(2., ratio), ratio, "Leading Edge",
        enabled=baseline.edges.le_type == EdgeType.ELLIPTICAL)
    te = baseline.thickness.points[-1].value
    add("te_thickness", min(.1,te), max(2.*te,1.), te, "Trailing Edge")
    if mode == OptimizationMode.ARCHITECTURE:
        g = baseline.geometry
        add("r_le", .9*g.r_le, 1.1*g.r_le, g.r_le, "Global Geometry")
        add("r_te", max(1.01*g.r_le,.9*g.r_te), max(1.1*g.r_te,1.02*g.r_le), g.r_te, "Global Geometry")
        # Ensure any valid baseline is inside its initial bounds.
        result[-1].lower = min(result[-1].lower,g.r_te)
        counts = tuple(range(max(1,g.vane_count-3),g.vane_count+4))
        result.append(OptimizationParameter("vane_count",ParameterType.DISCRETE,counts[0],counts[-1],
                                           g.vane_count,group="Vane Arrangement",choices=counts))
    return result
