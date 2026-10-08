"""Geometry-only screening. No CFD or optimizer dependency."""
from collections.abc import Sequence
import numpy as np
from ..geometry.distributions import distribution_interpolator
from ..models.parameters import BladeParameters
from ..models.geometry import BladeGeometry
from ..models.validation import is_finite_number
from ..geometry.designer import BladeDesigner
from ..geometry.thickness import thickness_interpolator
from ..geometry.checks import has_self_intersection
from ..geometry.resample import closed_contour
from .models import GeometryConstraints, ConstraintCheck, FeasibilityResult, CandidateResult
from .parameter_mapper import ParameterMapper


def angle_derivatives(design: BladeParameters, m_norm: np.ndarray) -> tuple[np.ndarray,np.ndarray]:
    points = design.blade_angle.points
    curve = distribution_interpolator([p.m_norm for p in points],[p.value for p in points])
    return curve(m_norm,1),curve(m_norm,2)


def maximum_angle_derivatives(design: BladeParameters) -> tuple[float,float]:
    """Exact one-sided polynomial extrema; catches spikes between master samples."""
    points = design.blade_angle.points
    curve = distribution_interpolator([p.m_norm for p in points],[p.value for p in points])
    gradient, second = 0.,0.
    for i,h in enumerate(np.diff(curve.x)):
        a,b,c,_ = curve.c[:,i]
        locations = [0.,float(h)]
        if a != 0 and 0 < -b/(3*a) < h:
            locations.append(float(-b/(3*a)))
        t = np.array(locations)
        gradient = max(gradient,float(np.max(np.abs(3*a*t*t+2*b*t+c))))
        second = max(second,abs(float(2*b)),abs(float(6*a*h+2*b)))
    return gradient,second


def _validate_constraints(constraints: GeometryConstraints) -> None:
    if not isinstance(constraints.no_self_intersection,bool):
        raise ValueError("No self intersection must be boolean.")
    for name,value in vars(constraints).items():
        if name == "no_self_intersection" or value is None:
            continue
        if not is_finite_number(value) or value < 0:
            raise ValueError(f"{name}: constraint must be nonnegative and finite, or None.")
    if constraints.minimum_throat is not None and constraints.maximum_throat is not None:
        if constraints.minimum_throat > constraints.maximum_throat:
            raise ValueError("Minimum throat cannot exceed maximum throat.")


def check_feasibility(design: BladeParameters, geometry: BladeGeometry,
                      constraints: GeometryConstraints) -> FeasibilityResult:
    _validate_constraints(constraints)
    checks = []
    def limit(name: str, actual: float | None, threshold: float | None, minimum: bool) -> None:
        if threshold is None:
            return
        passed = actual is not None and (actual >= threshold if minimum else actual <= threshold)
        checks.append(ConstraintCheck(name,passed,actual,threshold,
            "Unavailable for this geometry" if actual is None else ""))
    if constraints.no_self_intersection:
        contour,_ = closed_contour(geometry.master_surfaces)
        intersects = has_self_intersection(contour)
        checks.append(ConstraintCheck("No self intersection",not intersects,not intersects,True))
    cusp = any("cusp" in i.message.lower() for i in geometry.warnings)
    checks.append(ConstraintCheck("No surface cusp",not cusp,not cusp,True))
    curve = thickness_interpolator(design.thickness)
    roots = curve.derivative().roots(extrapolate=False)
    samples = np.r_[curve.x,roots[np.isfinite(roots) & (roots >= 0) & (roots <= 1)]]
    minimum_thickness = float(np.min(curve(samples)))
    limit("Minimum thickness [mm]",minimum_thickness,constraints.minimum_thickness,True)
    max_k = float(max(np.max(np.abs(geometry.curvature.ps_curvature)),np.max(np.abs(geometry.curvature.ss_curvature))))
    limit("Maximum PS/SS curvature [1/mm]",max_k,constraints.maximum_curvature,False)
    min_radius = float("inf") if max_k == 0 else 1/max_k
    limit("Minimum PS/SS curvature radius [mm]",min_radius,constraints.minimum_curvature_radius,True)
    throat = geometry.metrics.throat
    width = None if throat is None else throat.width
    # Edge location is diagnostic information, never a rejection condition.
    limit("Minimum throat [mm]",width,constraints.minimum_throat,True)
    limit("Maximum throat [mm]",width,constraints.maximum_throat,False)
    if width is not None:
        checks.append(ConstraintCheck("No adjacent contact",width > 1e-7,width,1e-7))
    limit("Minimum TE thickness [mm]",design.thickness.points[-1].value,constraints.minimum_te_thickness,True)
    first,second = maximum_angle_derivatives(design)
    limit("Maximum |dβm/dMnorm| [deg]",first,constraints.maximum_turning_gradient,False)
    limit("Maximum |d²βm/dMnorm²| [deg]",second,constraints.maximum_turning_second_derivative,False)
    return FeasibilityResult(checks)


def evaluate_candidate(mapper: ParameterMapper, vector: Sequence[float],
                       constraints: GeometryConstraints | None = None,
                       normalized: bool = True) -> CandidateResult:
    constraints = constraints or GeometryConstraints()
    _validate_constraints(constraints)
    design = None
    try:
        design = mapper.create_design(vector,normalized=normalized)
        geometry = BladeDesigner().generate(design)
        feasibility = check_feasibility(design,geometry,constraints)
        return CandidateResult(design,geometry,feasibility)
    except (ValueError,ArithmeticError) as exc:
        return CandidateResult(design,None,FeasibilityResult([
            ConstraintCheck("Geometry validation",False,None,None,str(exc))]))
