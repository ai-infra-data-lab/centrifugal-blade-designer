"""Main-blade-linked splitter sections. Pure geometry; one splitter per passage."""
import numpy as np
from copy import deepcopy
from .distributions import interpolate_beta_m_deg
from .thickness import generate_thickness
from ..models.parameters import BladeSection,BladeAngleParameters,ThicknessParameters,DistributionPoint
from .blade_section import generate_section
from .blade_edge import edge_endpoints
from ..models.parameters import EdgeType
from .tip_clearance import row_wall_parameters,blade_span_wall


def splitter_edit_points(points,start):
    """Visible LE-to-TE controls on the unchanged main-blade 0..1 axis.

    The interpolated LE is a display boundary until explicitly edited. Keep the
    original controls separately to preserve PCHIP slopes when copying/loading.
    """
    if not np.isfinite(start) or not 0<=start<1:
        raise ValueError('Splitter editing start must be in [0, 1).')
    active=deepcopy([p for p in points if p.m_norm>=start])
    if not active or active[0].m_norm!=start:
        value=float(interpolate_beta_m_deg(np.array([start]),points)[0])
        active.insert(0,DistributionPoint(start,value))
    return active


def generate_splitter(params,main):
    settings=params.splitter;edges=params.impeller_edges
    flow=np.linspace(0,1,params.resolution.wall_points)
    if not edges.legacy_uniform_sampling:
        flow=np.unique(np.r_[flow,edges.reference_le_fraction,edges.reference_te_fraction])
    hub_parameter,tip_parameter=row_wall_parameters(edges,flow,main)
    cutoff_radius=float(edge_endpoints(edges.trailing_edge,main.hub,main.shroud)[0,1])
    offset=params.rotation_direction.sign*2*np.pi/params.geometry.vane_count*settings.pitch_fraction
    result=[]
    for profile,section in zip(params.sections,main.sections):
        start=(1-profile.span)*settings.hub_start_fraction+profile.span*settings.tip_start_fraction
        wall=blade_span_wall(main,profile.span,hub_parameter,tip_parameter)
        design=independent_profile(settings.sections,profile) if settings.sections is not None else profile
        if settings.sections is not None:design=splitter_active_profile(design,start)
        splitter=generate_section(design,wall,edges.reference_le_fraction,edges.reference_te_fraction,
            0.,params.output_points,params.surface_mapping,params.resolution,flow,params.rotation_direction.sign,
            cutoff_radius=cutoff_radius if profile.edge_parameters.te_type==EdgeType.CUTOFF else None,
            start_fraction=start,thickness_scale=settings.thickness_scale,
            theta_te_rad=section.camber.theta_rad[-1]+offset,
            distributions_from_le=settings.sections is not None)
        result.append(splitter)
    return result


def splitter_active_profile(profile,start):
    """PCHIP on exactly the visible LE-to-TE controls, using the main kernel.

    Stored points retain the legacy main-blade 0..1 coordinates. An absent LE
    is seeded from the stored curve; upstream points never set local slopes.
    """
    result=deepcopy(profile)
    for name in ('blade_angle','thickness'):
        points=splitter_edit_points(getattr(profile,name).points,start)
        for point in points:point.m_blade_norm=(point.m_blade_norm-start)/(1-start)
        getattr(result,name).points=points
    return result


def independent_profile(profiles,main_profile):
    """Use stored controls; interpolate between stored spans when main spans change."""
    span=main_profile.span
    exact=next((s for s in profiles if s.span==span),None)
    if exact is not None:result=deepcopy(exact)
    else:
        lo=next(i-1 for i,s in enumerate(profiles) if s.span>span)
        a,b=profiles[lo:lo+2];weight=(span-a.span)/(b.span-a.span)
        distributions=[]
        for name,interpolate,cls in (("blade_angle",interpolate_beta_m_deg,BladeAngleParameters),
                                     ("thickness",lambda x,p:generate_thickness(x,p),ThicknessParameters)):
            pa,pb=getattr(a,name),getattr(b,name)
            x=np.unique([p.m_norm for p in pa.points+pb.points])
            va=interpolate(x,pa.points) if name=="blade_angle" else interpolate(x,pa)
            vb=interpolate(x,pb.points) if name=="blade_angle" else interpolate(x,pb)
            distributions.append(cls([DistributionPoint(float(t),float(v)) for t,v in zip(x,(1-weight)*va+weight*vb)]))
        result=BladeSection(span,*distributions)
    result.edge_parameters=deepcopy(main_profile.edge_parameters)
    return result
