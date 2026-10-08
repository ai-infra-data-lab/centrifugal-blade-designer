import numpy as np
from ..models.parameters import BladeParameters
from ..models.geometry import BladeGeometry, BladeSurfaceGeometry, CurvatureGeometry
from ..models.validation import validate_parameters, ValidationLevel, ValidationIssue
from .resolution import validate_resolution
from .camber import generate_camber, MASTER_POINTS
from .thickness import generate_thickness
from .surface import generate_surfaces
from .edges import generate_edge
from .curvature import calculate_curvature
from .throat import calculate_throat
from .metrics import calculate_metrics
from .resample import resample_surfaces
from .checks import check_geometry


class GeometryValidationError(ValueError):
    """Invalid parameters or degenerate geometry."""


def diffuser_design_parameters(params):
    """Adapter for the existing radial 2D engine and optimization mapper."""
    from copy import deepcopy
    from .blade_section import validate_section
    from ..models.parameters import BladeSection
    if not isinstance(params.diffuser_profile,BladeSection) or params.diffuser_profile.span!=0:
        raise ValueError("A diffuser profile with span 0 is required.")
    validate_section(params.diffuser_profile)
    result=deepcopy(params)
    result.sections[0]=deepcopy(params.diffuser_profile)
    return result


class BladeDesigner:
    def generate_diffuser(self,params):
        return self.generate(diffuser_design_parameters(params))

    def generate_3d(self,params):
        from .geometry_3d import generate_impeller
        return generate_impeller(params)

    def generate(self, params: BladeParameters) -> BladeGeometry:
        validate_resolution(params.resolution)
        issues = validate_parameters(params)
        errors = [i for i in issues if i.level == ValidationLevel.ERROR]
        if errors:
            raise GeometryValidationError("; ".join(f"{i.field}: {i.message}" for i in errors))
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                camber = generate_camber(params, params.resolution.profile_points)
                thickness = generate_thickness(camber.m_norm, params.thickness)
                ps, ss, mapping, ambiguous = generate_surfaces(camber, thickness, params.surface_mapping)
                direction = camber.theta_rad + camber.rotation_sign * camber.beta_m_rad
                tangent = np.column_stack((np.cos(direction), np.sin(direction)))
                le = generate_edge(np.array([camber.x[0], camber.y[0]]), tangent[0],
                                   ps.xy[0], ss.xy[0], params.edges.le_type, params.edges.le_ellipse_ratio, True, params.resolution.edge_points)
                te = generate_edge(np.array([camber.x[-1], camber.y[-1]]), tangent[-1],
                                   ps.xy[-1], ss.xy[-1], params.edges.te_type, params.edges.te_ellipse_ratio, False, params.resolution.edge_points)
                master = BladeSurfaceGeometry(ps, ss, le, te)
                curvature = CurvatureGeometry(camber.m_norm, calculate_curvature(ps), calculate_curvature(ss))
                issues.extend(check_geometry(master, curvature, thickness, direction, params.edges))
                throat = calculate_throat(master, params.geometry.vane_count)
                metrics = calculate_metrics(camber, le.xy[len(le.x)//2], te.xy[len(te.x)//2],
                                            params.geometry.vane_count, throat)
                output = resample_surfaces(master, params.output_points)
                if not all(np.all(np.isfinite(v)) for v in (curvature.ps_curvature, curvature.ss_curvature)):
                    raise ValueError("Non-finite curvature.")
        except (ValueError, FloatingPointError) as exc:
            raise GeometryValidationError(str(exc)) from exc
        if ambiguous:
            issues.append(ValidationIssue(ValidationLevel.WARNING, "surface_mapping",
                "Auto mapping is ambiguous (near-zero net turning); +Normal = PS selected. Use manual override."))
        if throat is None:
            issues.append(ValidationIssue(ValidationLevel.WARNING, "throat",
                "Throat unavailable: one blade has no distinct adjacent blade."))
        elif "TE" in (throat.blade1_segment, throat.blade2_segment):
            issues.append(ValidationIssue(ValidationLevel.WARNING, "throat",
                "Throat lies on trailing edge geometry"))
        if throat is not None and throat.width < 1e-7:
            issues.append(ValidationIssue(ValidationLevel.WARNING, "throat", "Adjacent blades touch or intersect."))
        return BladeGeometry(camber, output, curvature, metrics, master, thickness, mapping, issues)
