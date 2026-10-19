"""Configurable CSV of actual master curves; legacy exporters stay unchanged."""
import csv
from dataclasses import dataclass
import io
import os
from pathlib import Path
import tempfile
import numpy as np
from .csv_export import format_number
from .case_publish import staged_case, _write_case_files
from .row_xyz_csv import COLUMNS
from ..models.geometry_3d import Curve3D

COORDINATES = ('x_mm', 'y_mm', 'z_mm', 'r_mm', 'theta_deg', 'theta_rad', 'rtheta_mm')
METADATA = COLUMNS[:12]


@dataclass(frozen=True)
class CoordinateCsvOptions:
    columns: tuple[str, ...] = ('x_mm', 'y_mm', 'z_mm')
    split_spans: bool = False
    include_metadata: bool = True
    include_blades: bool = True
    include_hub: bool = False
    include_shroud: bool = False
    wall_layout: str = 'combined'
    extension: str = 'csv'
    shroud_source: str = 'drawing'

    @property
    def requires_directory(self):
        return self.split_spans or ((self.include_hub or self.include_shroud) and self.wall_layout != 'combined')

    def validate(self):
        if (not self.columns or any(c not in COORDINATES for c in self.columns)
                or len(set(self.columns)) != len(self.columns)):
            raise ValueError('Select unique coordinate columns in the required order.')
        if any(type(value) is not bool for value in (self.split_spans, self.include_metadata,
                self.include_blades, self.include_hub, self.include_shroud)):
            raise ValueError('CSV output switches must be boolean.')
        if not (self.include_blades or self.include_hub or self.include_shroud):
            raise ValueError('Select blades, Hub or Shroud for output.')
        if self.wall_layout not in ('combined', 'together', 'separate') or self.extension not in ('csv', 'txt'):
            raise ValueError('Invalid wall layout or file extension.')
        if self.shroud_source not in ('drawing','analysis','both'):
            raise ValueError('Invalid Shroud source.')
        if self.split_spans and (not self.include_blades or
                ((self.include_hub or self.include_shroud) and self.wall_layout == 'combined')):
            raise ValueError('Span splitting requires blades and a separate wall file layout.')


def prepare_coordinate_csv(geometry, source, options=None, significant_digits=15, *, wall_chunks=None):
    """Return complete UTF-8/BOM payloads, without touching the destination.

    Theta is the stored continuous angle about +Z (positive CCW); Rtheta uses
    that angle in radians and has units mm, irrespective of selected theta unit.
    No interpolation, annulus replication, closure or extra spans are introduced.
    """
    options = options or CoordinateCsvOptions()
    options.validate()
    fmt = lambda value: format_number(value, significant_digits)
    fmt(0.)
    if source.engine != 'meridional_3d' or (options.include_blades and not geometry.sections):
        raise ValueError('Coordinate CSV requires an actual meridional_3d master with main sections.')
    streams = {}
    writers = {}
    extension = options.extension

    def append_curve(name, curve, group, span, role):
        if name not in streams:
            streams[name] = io.StringIO(newline='')
            writers[name] = csv.writer(streams[name], delimiter='\t' if extension == 'txt' else ',')
            writers[name].writerow((METADATA if options.include_metadata else []) + list(options.columns))
        r = np.asarray(curve.r)
        theta = np.asarray(curve.theta_rad)
        z = np.asarray(curve.z)
        if (r.ndim != 1 or len(r) < 2 or theta.shape != r.shape or z.shape != r.shape
                or np.any(r < 0) or not all(np.all(np.isfinite(a)) for a in (r, theta, z))):
            raise ValueError('Invalid cylindrical coordinates in CSV.')
        xyz = curve.xyz
        if xyz.ndim != 2 or xyz.shape[1] != 3 or not np.all(np.isfinite(xyz)):
            raise ValueError('Coordinate CSV requires finite nonempty master curves.')
        with np.errstate(over='ignore', invalid='ignore'):
            values = dict(zip(('x_mm', 'y_mm', 'z_mm'), xyz.T))
            values.update(r_mm=r, theta_deg=np.rad2deg(theta), theta_rad=theta, rtheta_mm=r * theta)
        if not all(np.all(np.isfinite(values[c])) for c in options.columns):
            raise ValueError('Selected coordinate conversion is not finite.')
        u = curve.m_blade_norm
        if u is not None and (np.shape(u) != (len(xyz),) or not np.all(np.isfinite(u))):
            raise ValueError('Invalid streamwise coordinates in CSV.')
        for index in range(len(xyz)):
            metadata = [source.row_id, source.row_name, source.row_kind, source.engine, source.variant,
                        source.snapshot_hash, significant_digits, group, '' if span is None else fmt(span), role, index,
                        '' if u is None else fmt(u[index])] if options.include_metadata else []
            writers[name].writerow(metadata + [fmt(values[c][index]) for c in options.columns])

    groups = (('main', geometry.sections), ('splitter', geometry.splitter_sections)) if options.include_blades else ()
    for group, sections in groups:
        previous = -1.
        for ordinal, section in enumerate(sections or [], 1):
            span = section.span
            if not np.isfinite(span) or not previous < span <= 1 or span < 0:
                raise ValueError('CSV spans must be finite, unique and ordered within 0..1.')
            previous = span
            # Ordinal prevents collisions even at low numeric output precision.
            name = (f'{group}_span_{ordinal:03d}_{span:.15g}.{extension}' if options.split_spans
                    else f'coordinates.{extension}')
            for role in ('le', 'ps', 'te', 'ss'):
                append_curve(name, getattr(section, 'master_' + role), group, span, role.upper())
    walls=[('hub', options.include_hub)]
    walls.extend((key,options.include_shroud) for key in
                 (('shroud',) if options.shroud_source=='drawing' else ('analysis_shroud',)
                  if options.shroud_source=='analysis' else ('shroud','analysis_shroud')))
    for wall, enabled in walls:
        if not enabled:
            continue
        if wall=='analysis_shroud':
            data=getattr(geometry,'analysis_shroud',None)
            if data is None:raise ValueError('Enable a separate Analysis Shroud before exporting it.')
            chunks=[data.wall] if wall_chunks is None else wall_chunks.get(wall,[])
        else:
            chunks = ([getattr(geometry, wall)] if wall_chunks is None else wall_chunks.get(wall, []))
        if not chunks:
            raise ValueError(f'No {wall} wall is assigned to the selected row.')
        stem = ('coordinates' if options.wall_layout == 'combined' else
                'walls' if options.wall_layout == 'together' else wall)
        for ordinal, chunk in enumerate(chunks, 1):
            r = np.asarray(chunk.r)
            curve = Curve3D(r, np.zeros_like(r), np.asarray(chunk.z))
            append_curve(f'{stem}.{extension}', curve, wall, None, f'{wall.upper()}_{ordinal:03d}')
    return {name: stream.getvalue().encode('utf-8-sig') for name, stream in streams.items()}


def export_coordinate_csv(path, geometry, source, options=None, significant_digits=15, *, wall_chunks=None):
    """Single-file replacement is atomic; span bundles require a new directory."""
    options = options or CoordinateCsvOptions()
    contents = prepare_coordinate_csv(geometry, source, options, significant_digits, wall_chunks=wall_chunks)
    target = Path(path)
    if options.requires_directory:
        if target.exists():
            raise FileExistsError('Split output requires a new directory; choose a different name.')
        with staged_case(target) as stage:
            if target.exists():
                raise FileExistsError('Split output directory already exists.')
            _write_case_files(stage, contents)
        return [target / name for name in contents]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents['coordinates.' + options.extension])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return [target]
