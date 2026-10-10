"""Physical wall intervals selected by blade-row segment ownership (no Qt/I/O)."""
import numpy as np


def wall_interval(curve, geometry, identifier):
    indices = [i for i, segment in enumerate(curve.segments) if segment.blade_row == identifier]
    if not indices:
        raise ValueError("Assign Hub and Shroud segments to the selected blade row before exporting.")
    if indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError("A blade row must own one continuous interval on each wall.")
    boundaries = np.r_[0., np.cumsum([segment.length for segment in geometry.segments])]
    return float(boundaries[indices[0]]), float(boundaries[indices[-1] + 1])


def export_wall_intervals(params, geometry):
    if not any(segment.blade_row is not None for curve in (params.hub, params.shroud) for segment in curve.segments):
        return [(0., geometry.hub.length), (0., geometry.shroud.length)]
    if not params.active_blade_row:
        raise ValueError("Select a blade row for the assigned meridional export domain.")
    intervals = [wall_interval(curve, wall, params.active_blade_row)
                 for curve, wall in ((params.hub, geometry.hub), (params.shroud, geometry.shroud))]
    for (start, end), wall, side in zip(intervals, (geometry.hub, geometry.shroud), ("hub", "shroud")):
        leading = getattr(params.impeller_edges.leading_edge, side + "_m_flow_norm") * wall.length
        trailing = getattr(params.impeller_edges.trailing_edge, side + "_m_flow_norm") * wall.length
        if start > leading + 1e-9 or end < trailing - 1e-9:
            raise ValueError("The assigned meridional export domain must contain the blade LE and TE.")
        section = geometry.sections[0 if side == "hub" else -1]
        distances = np.concatenate([getattr(section, "master_" + name).meridional_distance
                                    for name in ("le", "ps", "te", "ss")])
        tolerance = wall.length * 1e-6  # sampled span-wall arc length versus analytic wall length
        if distances.min() < start - tolerance or distances.max() > end + tolerance:
            raise ValueError("The assigned meridional export domain must contain the complete blade profile.")
    return intervals
