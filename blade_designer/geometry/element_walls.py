"""Independent element walls and directed G1 connections; no Qt or file I/O."""
from copy import deepcopy
import numpy as np
from .meridional_segments import generate_meridional,validate_flow_path
from ..models.geometry_3d import ImpellerGeometry


def wall_domain_indices(curve, identifier):
    assigned=any(segment.blade_row is not None for segment in curve.segments)
    indices=[i for i,segment in enumerate(curve.segments) if segment.blade_row==identifier]
    if not assigned:return 0,len(curve.segments)-1
    if not indices or indices!=list(range(indices[0],indices[-1]+1)):
        raise ValueError('Assign one continuous wall interval to the element before connecting it.')
    return indices[0],indices[-1]


def connect_curves(parameters, identifier, upstream, upstream_id):
    result=[]
    for name in ('hub','shroud'):
        definition=deepcopy(getattr(parameters,name));parent_definition=getattr(upstream,name)
        geometry=generate_meridional(definition);parent=generate_meridional(parent_definition)
        inlet,_=wall_domain_indices(definition,identifier)
        _,outlet=wall_domain_indices(parent_definition,upstream_id)
        source=geometry.segments[inlet];target=parent.segments[outlet]
        angle=float(np.arctan2(target.end_tangent[1],target.end_tangent[0])-
                    np.arctan2(source.start_tangent[1],source.start_tangent[0]))
        c,s=np.cos(angle),np.sin(angle);rotation=np.array([[c,-s],[s,c]])
        start=target.end.zr+rotation@(geometry.segments[0].start.zr-source.start.zr)
        definition.start_z,definition.start_r=map(float,start)
        definition.start_angle_deg+=float(np.rad2deg(angle))
        checked=generate_meridional(definition).segments[inlet]
        if (not np.allclose(checked.start.zr,target.end.zr,rtol=0,atol=1e-8) or
                not np.allclose(checked.start_tangent,target.end_tangent,rtol=0,atol=1e-10)):
            raise ValueError('Element G0/G1 connection could not be established.')
        result.append(definition)
    return tuple(result)


def generate_wall_element(parameters):
    parameters=effective_wall_parameters(parameters)
    hub,shroud=generate_meridional(parameters.hub),generate_meridional(parameters.shroud)
    validate_flow_path(hub,shroud)
    return ImpellerGeometry(hub,shroud,[])


def effective_wall_parameters(project):
    from ..models.blade_rows import row_parameters
    active=next((row for row in project.blade_rows or [] if row.identifier==project.active_blade_row),None)
    if active is None or not active.independent_meridional:return project
    result=row_parameters(project,active)
    result.active_blade_row=active.identifier
    return result
