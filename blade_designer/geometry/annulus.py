from dataclasses import dataclass
import numpy as np
from ..models.geometry import FloatArray, BladeGeometry
from .resample import closed_contour


@dataclass
class AnnulusBlade:
    index: int
    angle_rad: float
    x: FloatArray
    y: FloatArray


def rotate_xy(x: FloatArray, y: FloatArray, angle_rad: float) -> tuple[FloatArray, FloatArray]:
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return x*c - y*s, x*s + y*c


def project_annulus(x: FloatArray, y: FloatArray, z: FloatArray,
                    blade_count: int, projection: str = "XY") -> tuple[FloatArray, FloatArray]:
    """Rotate physical XYZ coordinates around Z, then project each blade.

    NaN separators are exclusively for drawing disconnected preview polylines.
    """
    if not isinstance(blade_count, int) or isinstance(blade_count, bool) or blade_count < 1:
        raise ValueError("Blade count must be a positive integer.")
    if projection not in ("XY", "XZ", "YZ"):
        raise ValueError("Projection must be XY, XZ or YZ.")
    x, y, z = (np.asarray(values, dtype=np.float64) for values in (x, y, z))
    if x.ndim != 1 or not (x.shape == y.shape == z.shape) or not len(x):
        raise ValueError("Annulus coordinates must be nonempty matching one-dimensional arrays.")
    if not all(np.isfinite(values).all() for values in (x, y, z)):
        raise ValueError("Annulus coordinates must be finite.")
    horizontal, vertical = [], []
    for index in range(blade_count):
        rotated_x, rotated_y = rotate_xy(x, y, 2*np.pi*index/blade_count)
        coordinates = {"X": rotated_x, "Y": rotated_y, "Z": z}
        horizontal.append(np.r_[coordinates[projection[0]], np.nan])
        vertical.append(np.r_[coordinates[projection[1]], np.nan])
    return np.concatenate(horizontal), np.concatenate(vertical)


def generate_annulus(blade: BladeGeometry, vane_count: int) -> list[AnnulusBlade]:
    if not isinstance(vane_count, int) or isinstance(vane_count, bool) or vane_count < 1:
        raise ValueError("Vane count must be a positive integer.")
    xy, _ = closed_contour(blade.surfaces, repeat_first=True)
    return [AnnulusBlade(k, angle := 2*np.pi*k/vane_count, *rotate_xy(xy[:,0], xy[:,1], angle))
            for k in range(vane_count)]
