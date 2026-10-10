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


def row_parameters(project, row):
    result = row_snapshot(row.parameters)
    for name in SHARED_FIELDS:
        setattr(result, name, deepcopy(getattr(project, name)))
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
        if not isinstance(row, BladeRow) or row.kind not in ("impeller", "diffuser"):
            raise ValueError("Unknown blade row type.")
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
    for curve in (project.hub, project.shroud):
        for segment in curve.segments:
            if segment.blade_row is not None and segment.blade_row not in identifiers:
                raise ValueError("Meridional segment references an unknown blade row.")
