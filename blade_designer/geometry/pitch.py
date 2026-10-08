import numpy as np
from ..models.geometry import FloatArray


def angular_pitch(vane_count: int) -> float:
    if vane_count < 1:
        raise ValueError("Vane count must be positive.")
    return 2 * np.pi / vane_count


def linear_pitch(radius: FloatArray | float, vane_count: int) -> FloatArray | float:
    return angular_pitch(vane_count) * radius
