import numpy as np
from copy import deepcopy
from ..models.geometry_3d import ImpellerGeometry
from ..models.validation import validate_row_settings,ValidationLevel
from .meridional_segments import generate_meridional,validate_flow_path
from .flow_path import validate_component_stations
from .resolution import validate_resolution
from .blade_section import generate_section
from ..models.parameters import EdgeType,BladeSection
from .tip_clearance import make_tip_geometry,row_wall_parameters,blade_span_wall


def generate_impeller(params):
    geometry=_generate_row(params,params.sections,params.impeller_edges,impeller_cutoff=True)
    if params.impeller_te_rake_deg is not None:
        from .impeller_parameter_mapper import ImpellerParameterMapper
        geometry=ImpellerParameterMapper.map_te_rake(geometry,params.impeller_te_rake_deg)
    if params.splitter is not None:
        from .splitter import generate_splitter
        geometry.splitter_sections=generate_splitter(params,geometry)
    from .impeller_trim import apply_trim
    geometry=apply_trim(geometry,params)
    from .analysis_shroud import make_analysis_shroud
    geometry.analysis_shroud=make_analysis_shroud(params,geometry)
    return geometry


def generate_diffuser_3d(params):
    """Use the shared diffuser distribution on Hub and Shroud walls."""
    if not isinstance(params.diffuser_profile,BladeSection) or params.diffuser_profile.span!=0:
        raise ValueError("A diffuser profile with span 0 is required.")
    sections=[]
    for span in (0.,1.):
        section=deepcopy(params.diffuser_profile);section.span=span;sections.append(section)
    return _generate_row(params,sections,params.diffuser_edges)


def _generate_row(params,profiles,edges,*,impeller_cutoff=False):
    validate_resolution(params.resolution)
    kind="impeller" if impeller_cutoff else "diffuser"
    errors=[i.message for i in validate_row_settings(params,kind) if i.level==ValidationLevel.ERROR]
    if errors: raise ValueError('; '.join(errors))
    if not profiles or len(profiles)<2:
        raise ValueError("At least Hub and Tip sections are required.")
    spans=np.asarray([s.span for s in profiles],dtype=float)
    if not np.all(np.isfinite(spans)) or spans[0]!=0 or spans[-1]!=1 or np.any(np.diff(spans)<=0):
        raise ValueError("Sections must increase strictly from Hub (0) to Tip (1).")
    validate_component_stations(params.flow_path)
    hub=generate_meridional(params.hub);shroud=generate_meridional(params.shroud)
    validate_flow_path(hub,shroud)
    from .blade_edge import validate_blade_edges,validate_blade_edge_bounds,edge_endpoints
    for candidate in (params.impeller_edges,params.diffuser_edges):
        validate_blade_edge_bounds(candidate)
    validate_blade_edges(edges,hub,shroud)
    cutoff_radius=float(edge_endpoints(edges.trailing_edge,hub,shroud)[0,1])
    le_reference,te_reference=edges.reference_le_fraction,edges.reference_te_fraction
    flow_coordinates=np.linspace(0,1,params.resolution.wall_points)
    if not edges.legacy_uniform_sampling:
        flow_coordinates=np.unique(np.r_[flow_coordinates,le_reference,te_reference])
    geometry=ImpellerGeometry(hub,shroud,[])
    if impeller_cutoff:geometry.tip=make_tip_geometry(params,hub,shroud)
    hub_parameter,shroud_parameter=row_wall_parameters(edges,flow_coordinates,geometry)
    sections=[]
    for section in profiles:
        wall_zr=blade_span_wall(geometry,section.span,hub_parameter,shroud_parameter)
        sections.append(generate_section(section,wall_zr,le_reference,te_reference,
            np.deg2rad(params.geometry.theta_le_deg),params.output_points,params.surface_mapping,params.resolution,flow_coordinates,params.rotation_direction.sign,
            cutoff_radius=cutoff_radius if impeller_cutoff and section.edge_parameters.te_type == EdgeType.CUTOFF else None))
    geometry.sections=sections
    return geometry
