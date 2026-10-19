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

COORDINATES = ('x_mm', 'y_mm', 'z_mm', 'r_mm', 'theta_deg', 'theta_rad', 'rtheta_mm')
METADATA = COLUMNS[:12]


@dataclass(frozen=True)
class CoordinateCsvOptions:
    columns: tuple[str, ...] = ('x_mm', 'y_mm', 'z_mm')
    split_spans: bool = False
    include_metadata: bool = True

    def validate(self):
        if (not self.columns or any(c not in COORDINATES for c in self.columns)
                or len(set(self.columns)) != len(self.columns)):
            raise ValueError('Select unique coordinate columns in the required order.')
        if type(self.split_spans) is not bool or type(self.include_metadata) is not bool:
            raise ValueError('CSV output switches must be boolean.')


def prepare_coordinate_csv(geometry, source, options=None, significant_digits=15):
    """Return complete UTF-8/BOM payloads, without touching the destination.

    Theta is the stored continuous angle about +Z (positive CCW); Rtheta uses
    that angle in radians and has units mm, irrespective of selected theta unit.
    No interpolation, annulus replication, closure or extra spans are introduced.
    """
    options = options or CoordinateCsvOptions()
    options.validate()
    fmt = lambda value: format_number(value, significant_digits)
    fmt(0.)
    if source.engine != 'meridional_3d' or not geometry.sections:
        raise ValueError('Coordinate CSV requires an actual meridional_3d master with main sections.')
    streams = {}
    writers = {}
    for group, sections in (('main', geometry.sections), ('splitter', geometry.splitter_sections)):
        previous = -1.
        for ordinal, section in enumerate(sections or [], 1):
            span = section.span
            if not np.isfinite(span) or not previous < span <= 1 or span < 0:
                raise ValueError('CSV spans must be finite, unique and ordered within 0..1.')
            previous = span
            # Ordinal prevents collisions even at low numeric output precision.
            name = f'{group}_span_{ordinal:03d}_{span:.15g}.csv' if options.split_spans else 'coordinates.csv'
            if name not in streams:
                streams[name] = io.StringIO(newline='')
                writers[name] = csv.writer(streams[name])
                writers[name].writerow((METADATA if options.include_metadata else []) + list(options.columns))
            writer = writers[name]
            for role in ('le', 'ps', 'te', 'ss'):
                curve = getattr(section, 'master_' + role)
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
                                source.snapshot_hash, significant_digits, group, fmt(span), role.upper(), index,
                                '' if u is None else fmt(u[index])] if options.include_metadata else []
                    writer.writerow(metadata + [fmt(values[c][index]) for c in options.columns])
    return {name: stream.getvalue().encode('utf-8-sig') for name, stream in streams.items()}


def export_coordinate_csv(path, geometry, source, options=None, significant_digits=15):
    """Single-file replacement is atomic; span bundles require a new directory."""
    options = options or CoordinateCsvOptions()
    contents = prepare_coordinate_csv(geometry, source, options, significant_digits)
    target = Path(path)
    if options.split_spans:
        if target.exists():
            raise FileExistsError('Span output requires a new directory; choose a different name.')
        with staged_case(target) as stage:
            if target.exists():
                raise FileExistsError('Span output directory already exists.')
            _write_case_files(stage, contents)
        return [target / name for name in contents]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents['coordinates.csv'])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return [target]
