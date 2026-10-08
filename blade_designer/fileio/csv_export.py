from pathlib import Path
import csv
import numpy as np
from ..models.geometry import BladeGeometry
from ..models.parameters import ExportParameters
from ..geometry.resample import closed_contour

SEGMENT_COLUMNS = ["segment", "index", "segment_fraction", "m_norm", "x", "y", "r", "theta_deg"]
SURFACE_COLUMNS = ["beta_m_deg", "thickness", "curvature"]
CONTOUR_COLUMNS = ["index", "segment", "x", "y", "r", "theta_deg"]


def format_number(value: float, significant_digits: int) -> str:
    if isinstance(significant_digits, bool) or not isinstance(significant_digits, int) or not 1 <= significant_digits <= 15:
        raise ValueError("Significant digits must be an integer from 1 to 15.")
    return format(float(value), f".{significant_digits}g")


def export_segments_csv(path: str | Path, blade: BladeGeometry,
                        settings: ExportParameters | None = None, include_surface_data: bool = True) -> None:
    settings = settings or ExportParameters()
    fmt = lambda v: format_number(v, settings.significant_digits)
    format_number(0., settings.significant_digits)
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(SEGMENT_COLUMNS + (SURFACE_COLUMNS if include_surface_data else []))
        for name in ("LE", "PS", "TE", "SS"):
            segment = getattr(blade.surfaces, name.lower())
            for i, (x, y) in enumerate(segment.xy):
                m = None if segment.m_norm is None else float(segment.m_norm[i])
                row = [name, i, fmt(i/(len(segment.x)-1)), "" if m is None else fmt(m),
                       fmt(x), fmt(y), fmt(np.hypot(x,y)), fmt(np.rad2deg(np.arctan2(y,x)))]
                if include_surface_data:
                    if m is None:
                        row += ["", "", ""]
                    else:
                        k = getattr(blade.curvature, name.lower() + "_curvature")
                        row += [fmt(np.interp(m, blade.camber.m_norm, np.rad2deg(blade.camber.beta_m_rad))),
                                fmt(np.interp(m, blade.camber.m_norm, blade.thickness)),
                                fmt(np.interp(m, blade.curvature.m_norm, k))]
                writer.writerow(row)


def export_contour_csv(path: str | Path, blade: BladeGeometry, settings: ExportParameters | None = None) -> None:
    settings = settings or ExportParameters()
    fmt = lambda v: format_number(v, settings.significant_digits)
    format_number(0., settings.significant_digits)
    xy, labels = closed_contour(blade.surfaces, settings.repeat_first_point)
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(CONTOUR_COLUMNS)
        for i, ((x,y), name) in enumerate(zip(xy, labels)):
            writer.writerow([i, name, fmt(x), fmt(y), fmt(np.hypot(x,y)), fmt(np.rad2deg(np.arctan2(y,x)))])
