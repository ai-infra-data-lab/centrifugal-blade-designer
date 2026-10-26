"""Independent blade-row snapshots; shared walls remain project properties."""
from copy import deepcopy
from .parameters import BladeRow, BladeParameters

SHARED_FIELDS = ("hub", "shroud", "flow_path", "resolution")


def row_snapshot(parameters):
    result = deepcopy(parameters)
    result.blade_rows = None
    result.active_blade_row = None
    return result


def initial_rows(parameters):
    return [BladeRow("row-1", "Impeller", "impeller", row_snapshot(parameters)),
            BladeRow("row-2", "Diffuser", "diffuser", row_snapshot(parameters))]


def visible_edge_rows(rows,active_identifier):
    """Owners of the two edge groups displayed in the meridional editor."""
    result={}
    for kind in ("impeller","diffuser"):
        candidates=[row for row in rows or [] if row.kind==kind]
        if candidates:
            result[kind+"_edges"]=next((row for row in candidates if row.identifier==active_identifier),candidates[0])
    return result


def reconcile_visible_row_edges(parameters):
    """Retain loaded top-level edge values when old row snapshots disagree.

    Only the selected/first row represented by each visible group is updated;
    other rows of the same kind retain their independent edge settings.
    """
    result=deepcopy(parameters)
    active=next((row for row in result.blade_rows or [] if row.identifier==result.active_blade_row),None)
    if active is not None and active.independent_meridional:
        return result  # New independent rows own their edges; the shared editor is a different domain.
    for key,row in visible_edge_rows(result.blade_rows,result.active_blade_row).items():
        setattr(row.parameters,key,deepcopy(getattr(result,key)))
    return result


def row_parameters(project, row, _trail=()):
    if row.identifier in _trail:
        raise ValueError('Meridional connections contain a cycle.')
    result = row_snapshot(row.parameters)
    for name in SHARED_FIELDS:
        if row.independent_meridional and name in ('hub','shroud'):
            continue
        setattr(result, name, deepcopy(getattr(project, name)))
    if row.upstream_row is not None:
        parent=next((item for item in project.blade_rows or [] if item.identifier==row.upstream_row),None)
        if parent is None:raise ValueError('Upstream element is missing.')
        upstream=row_parameters(project,parent,_trail+ (row.identifier,))
        from ..geometry.element_walls import connect_curves
        result.hub,result.shroud=connect_curves(result,row.identifier,upstream,parent.identifier,
            row.hub_inlet_turn_deg,row.shroud_inlet_turn_deg)
    return result


def validate_rows(project):
    rows = project.blade_rows
    if rows is None:
        if project.active_blade_row is not None:
            raise ValueError("Active blade row requires a row list.")
        return
    if not isinstance(rows, list) or not rows:
        raise ValueError("At least one blade row is required.")
    identifiers = []
    for row in rows:
        if not isinstance(row, BladeRow) or row.kind not in ("impeller", "diffuser", "meridional"):
            raise ValueError("Unknown blade row type.")
        if type(row.independent_meridional) is not bool:
            raise ValueError('Independent meridional flag must be boolean.')
        from ..geometry.meridional_segments import join_turn_radians
        for value in (row.hub_inlet_turn_deg,row.shroud_inlet_turn_deg):join_turn_radians(value)
        if not row.independent_meridional and any(value is not None for value in (row.hub_inlet_turn_deg,row.shroud_inlet_turn_deg)):
            raise ValueError('Element inlet angles require independent walls.')
        if row.kind=='meridional' and not row.independent_meridional:
            raise ValueError('A meridional-only element requires independent Hub/Shroud.')
        if row.upstream_row is not None and (not isinstance(row.upstream_row,str) or not row.independent_meridional):
            raise ValueError('An upstream connection requires independent Hub/Shroud.')
        if not isinstance(row.identifier, str) or not row.identifier or row.identifier in identifiers:
            raise ValueError("Blade row identifiers must be unique nonempty strings.")
        if not isinstance(row.name, str) or not row.name.strip():
            raise ValueError("Blade row name is required.")
        if not isinstance(row.parameters, BladeParameters):
            raise ValueError("Blade row parameters are required.")
        if row.parameters.blade_rows is not None or row.parameters.active_blade_row is not None:
            raise ValueError("Nested blade row lists are forbidden.")
        identifiers.append(row.identifier)
    if project.active_blade_row not in identifiers:
        raise ValueError("Active blade row is missing from the row list.")
    links={row.identifier:row.upstream_row for row in rows}
    for identifier in identifiers:
        seen=set();current=identifier
        while current is not None:
            if current not in links:raise ValueError('Upstream element is missing.')
            if current in seen:raise ValueError('Meridional connections contain a cycle.')
            seen.add(current);current=links[current]
    for curve in (project.hub, project.shroud):
        for segment in curve.segments:
            if segment.blade_row is not None and segment.blade_row not in identifiers:
                raise ValueError("Meridional segment references an unknown blade row.")
    for row in rows:
        if row.independent_meridional:
            for curve in (row.parameters.hub,row.parameters.shroud):
                if any(segment.blade_row is not None and segment.blade_row not in identifiers for segment in curve.segments):
                    raise ValueError('Independent wall references an unknown element.')
