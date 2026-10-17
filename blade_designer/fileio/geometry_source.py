"""Bind result identities to the same canonical snapshot used by CAD jobs."""
from dataclasses import asdict
import hashlib
from ..cad.client import json_text
from ..models.geometry_source import GeometrySource
from ..models.blade_rows import validate_rows


def geometry_source(project, engine, *, kind='impeller', variant='base'):
    validate_rows(project)
    row = (next(r for r in project.blade_rows if r.identifier == project.active_blade_row)
           if project.blade_rows is not None else None)
    snapshot = {'schema_version': '0.4', **asdict(project)}
    digest = hashlib.sha256(json_text(snapshot).encode('utf-8')).hexdigest()
    return GeometrySource(row.identifier if row else 'unassigned', row.name if row else kind.title(),
                          row.kind if row else kind, engine, variant, digest)
