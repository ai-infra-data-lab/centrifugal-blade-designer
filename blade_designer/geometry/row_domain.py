"""Physical wall intervals selected by blade-row segment ownership (no Qt/I/O)."""
import numpy as np
from types import SimpleNamespace
from .meridional_segments import sample_meridional


def preview_wall_chunks(params,geometry,identifier):
    """Sample owned wall runs without joining gaps or changing design geometry.

    Legacy projects with no ownership use the full walls. Unlike export, a
    preview can display disconnected or partially assigned wall segments.
    """
    assigned=any(s.blade_row is not None for c in (params.hub,params.shroud) for s in c.segments)
    result={}
    for name in ("hub","shroud"):
        wall=getattr(geometry,name);curve=getattr(params,name)
        if not assigned:
            result[name]=[wall];continue
        boundaries=np.r_[0.,np.cumsum([s.length for s in wall.segments])]
        if hasattr(wall,'source_m'):
            boundaries=np.interp(wall.source_boundaries,wall.source_m,wall.m)
        indices=[i for i,s in enumerate(curve.segments) if s.blade_row==identifier]
        runs=[]
        for i in indices:
            if runs and runs[-1][-1]+1==i:runs[-1].append(i)
            else:runs.append([i])
        chunks=[]
        for run in runs:
            start,end=boundaries[run[0]],boundaries[run[-1]+1]
            # Include joins exactly so a short line/arc never disappears.
            distances=np.unique(np.r_[np.linspace(start,end,49),boundaries[run[0]:run[-1]+2]])
            zr=sample_meridional(wall,distances)
            chunks.append(SimpleNamespace(z=zr[:,0],r=zr[:,1]))
        result[name]=chunks
    return result


def wall_interval(curve, geometry, identifier):
    indices = [i for i, segment in enumerate(curve.segments) if segment.blade_row == identifier]
    if not indices:
        raise ValueError("Assign Hub and Shroud segments to the selected blade row before exporting.")
    if indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError("A blade row must own one continuous interval on each wall.")
    boundaries = np.r_[0., np.cumsum([segment.length for segment in geometry.segments])]
    return float(boundaries[indices[0]]), float(boundaries[indices[-1] + 1])


def export_wall_intervals(params, geometry, edges=None):
    edges = params.impeller_edges if edges is None else edges
    if not any(segment.blade_row is not None for curve in (params.hub, params.shroud) for segment in curve.segments):
        return [(0., geometry.hub.length), (0., geometry.shroud.length)]
    if not params.active_blade_row:
        raise ValueError("Select a blade row for the assigned meridional export domain.")
    intervals = [wall_interval(curve, wall, params.active_blade_row)
                 for curve, wall in ((params.hub, geometry.hub), (params.shroud, geometry.shroud))]
    for (start, end), wall, side in zip(intervals, (geometry.hub, geometry.shroud), ("hub", "shroud")):
        leading = getattr(edges.leading_edge, side + "_m_flow_norm") * wall.length
        trailing = getattr(edges.trailing_edge, side + "_m_flow_norm") * wall.length
        if start > leading + 1e-9 or end < trailing - 1e-9:
            raise ValueError("The assigned meridional export domain must contain the blade LE and TE.")
        section = geometry.sections[0 if side == "hub" else -1]
        distances = np.concatenate([getattr(section, "master_" + name).meridional_distance
                                    for name in ("le", "ps", "te", "ss")])
        tolerance = wall.length * 1e-6  # sampled span-wall arc length versus analytic wall length
        if distances.min() < start - tolerance or distances.max() > end + tolerance:
            raise ValueError("The assigned meridional export domain must contain the complete blade profile.")
    return intervals
