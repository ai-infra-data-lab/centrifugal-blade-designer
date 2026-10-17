"""Explicit actual-master XYZ export; legacy XY CSV writers stay unchanged."""
import csv
import io
import os
from pathlib import Path
import tempfile
import numpy as np
from .csv_export import format_number

COLUMNS = ['row_id', 'row_name', 'row_kind', 'engine', 'variant', 'snapshot_hash',
           'significant_digits', 'blade_set', 'span', 'segment', 'index', 'm_blade_norm',
           'x_mm', 'y_mm', 'z_mm', 'r_mm', 'theta_deg']


def prepare_row_xyz_csv(geometry, source, significant_digits=15):
    if source.engine != 'meridional_3d':
        raise ValueError('Actual XYZ CSV requires a meridional_3d source.')
    fmt = lambda value: format_number(value, significant_digits)
    fmt(0.)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(COLUMNS)
    for group, sections in (('main', geometry.sections), ('splitter', geometry.splitter_sections)):
        for section in sections or []:
            for role in ('le', 'ps', 'te', 'ss'):
                curve = getattr(section, 'master_'+role)
                xyz = curve.xyz
                if xyz.ndim != 2 or xyz.shape[1] != 3 or len(xyz) < 2 or not np.all(np.isfinite(xyz)):
                    raise ValueError('Actual XYZ CSV requires finite nonempty master curves.')
                u = curve.m_blade_norm
                if u is not None and (len(u) != len(xyz) or not np.all(np.isfinite(u))):
                    raise ValueError('Invalid streamwise coordinates in XYZ CSV.')
                for index, (x, y, z) in enumerate(xyz):
                    writer.writerow([source.row_id, source.row_name, source.row_kind, source.engine,
                                     source.variant, source.snapshot_hash, significant_digits, group, fmt(section.span),
                                     role.upper(), index, '' if u is None else fmt(u[index]),
                                     fmt(x), fmt(y), fmt(z), fmt(curve.r[index]), fmt(np.rad2deg(curve.theta_rad[index]))])
    if not geometry.sections:
        raise ValueError('Actual XYZ CSV requires at least one main section.')
    return stream.getvalue().encode('utf-8-sig')


def export_row_xyz_csv(path, geometry, source, significant_digits=15):
    data = prepare_row_xyz_csv(geometry, source, significant_digits)
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
