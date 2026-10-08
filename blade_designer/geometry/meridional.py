import numpy as np
from ..models.geometry import FloatArray


def calculate_meridional(r: FloatArray, z: FloatArray) -> tuple[FloatArray, FloatArray]:
    r, z = np.asarray(r, dtype=float), np.asarray(z, dtype=float)
    if r.ndim != 1 or r.shape != z.shape or len(r) < 2 or not np.all(np.isfinite([r, z])):
        raise ValueError("Meridional geometry requires matching finite R/Z arrays.")
    dm = np.hypot(np.diff(r), np.diff(z))
    if np.any(dm <= 0):
        raise ValueError("Meridional geometry contains repeated points.")
    m = np.r_[0., np.cumsum(dm)]
    return m, m / m[-1]
