"""Preserve earlier v0.3 blade coordinates while separating boundary data."""
from copy import deepcopy
from dataclasses import asdict
import numpy as np

def migrate_v03_blade_edges(data):
    result=deepcopy(data)
    result.setdefault("rotation_direction","ccw")
    if all(k in result for k in ("impeller_edges","diffuser_edges")):return result
    from .project_io import _curve
    from ..geometry.meridional_segments import generate_meridional
    from ..geometry.station_alignment import blade_station_wall_parameters
    from ..geometry.flow_path import sample_mean_line
    from ..models.flow_path import FlowPathParameters,ComponentStation,StationType
    from ..models.blade_edge import BladeRowEdgeParameters,BladeEdgePosition
    hub,shroud=[generate_meridional(_curve(result[k])) for k in ("hub","shroud")]
    fp=result["flow_path"]
    flow=FlowPathParameters([ComponentStation(StationType(s["kind"]),s["m_flow_norm"]) for s in fp["stations"]],fp["align_blade_stations_to_crossflow"])
    for key,kinds in (("impeller_edges",(StationType.IMP_LE,StationType.IMP_TE)),("diffuser_edges",(StationType.DIF_LE,StationType.DIF_TE))):
        if key in result:continue
        le,te=[flow.position(k) for k in kinds]
        refs,_,_,_=sample_mean_line(hub,shroud,np.array([le,te]),result["resolution"]["mean_points"])
        uniform=not flow.align_blade_stations_to_crossflow
        if uniform:
            h=s=refs;le,te=refs
        elif key=="impeller_edges":
            h,s=blade_station_wall_parameters(hub,shroud,flow,np.array([le,te]),result["resolution"]["mean_points"])
        else:
            # No legacy diffuser 3D profiles exist; initialize wall arc positions.
            h=s=refs
        result[key]=asdict(BladeRowEdgeParameters(BladeEdgePosition(float(h[0]),float(s[0])),
            BladeEdgePosition(float(h[1]),float(s[1])),float(le),float(te),uniform))
    return result
