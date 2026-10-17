"""Explicitly provisional mechanical dimensions; no Qt or CAD kernel dependency."""
import numpy as np
from ..models.cad import DiskGeometryParameters
from ..models.meridional import MeridionalCurveParameters,LineSegmentParameters
from ..models.blade_rows import row_parameters
from .geometry_3d import generate_impeller
from .meridional_segments import sample_meridional
from .blade_edge import project_to_wall


def hub_blade_extent(geometry):
    """Use actual root coordinates; legacy sampling metadata is not arclength."""
    roots=[geometry.sections[0]]
    if geometry.splitter_sections:roots.append(geometry.splitter_sections[0])
    return max(project_to_wall(geometry.hub,(z,r))[0]*geometry.hub.length
        for root in roots for role in ('le','ps','te','ss')
        for z,r in zip(getattr(root,'master_'+role).z,getattr(root,'master_'+role).r))


def make_provisional_disk(project):
    params=project
    if project.blade_rows is not None:
        row=next(row for row in project.blade_rows if row.identifier==project.active_blade_row)
        if row.kind!='impeller':raise ValueError('A provisional disk requires an Impeller row.')
        params=row_parameters(project,row)
    geometry=generate_impeller(params);hub=geometry.hub
    trailing=hub_blade_extent(geometry)
    end=min(hub.length,trailing+10.)
    distances=np.unique(np.r_[hub.m[hub.m<=end],end])
    points=sample_meridional(hub,distances)
    bore=max(0.,min(10.,float(points[:,1].min())*.25))
    outer=float(points[-1,1])
    hub_z=float(geometry.sections[0].camber.z[-1]);tip_z=float(geometry.sections[-1].camber.z[-1])
    direction=hub_z-tip_z
    if abs(direction)<1e-9:direction=float(points[-1,0]-points[0,0]) or 1.
    back_z=float(points[:,0].max())+20. if direction>0 else float(points[:,0].min())-20.
    if outer<=bore:raise ValueError('The provisional disk needs a positive radial backside width.')
    backside=MeridionalCurveParameters(back_z,outer,-90.,[LineSegmentParameters(outer-bore)])
    return DiskGeometryParameters(backside,bore,provisional=True,front_end_m_mm=float(end))
