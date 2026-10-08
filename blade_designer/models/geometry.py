from dataclasses import dataclass, field
import numpy as np
from numpy.typing import NDArray
from .parameters import SurfaceMapping
from .validation import ValidationIssue

FloatArray = NDArray[np.float64]


@dataclass
class CamberGeometry:
    m_norm: FloatArray
    m: FloatArray
    r: FloatArray
    theta_rad: FloatArray
    beta_m_rad: FloatArray
    x: FloatArray
    y: FloatArray
    rotation_sign: float = 1.


@dataclass
class BladeSegment:
    x: FloatArray
    y: FloatArray
    m_norm: FloatArray | None = None

    @property
    def xy(self) -> FloatArray:
        return np.column_stack((self.x, self.y))


@dataclass
class BladeSurfaceGeometry:
    ps: BladeSegment
    ss: BladeSegment
    le: BladeSegment
    te: BladeSegment


@dataclass
class ThroatResult:
    width: float
    blade1_x: float
    blade1_y: float
    blade2_x: float
    blade2_y: float
    blade1_segment: str
    blade2_segment: str
    m_norm_1: float | None
    m_norm_2: float | None


@dataclass
class BladeMetrics:
    chord: float
    camber_length: float
    angular_pitch_deg: float
    pitch_le: float
    pitch_mid: float
    pitch_te: float
    solidity_le: float
    solidity_mid: float
    solidity_te: float
    throat: ThroatResult | None
    throat_pitch: float | None
    throat_pitch_ratio: float | None


@dataclass
class CurvatureGeometry:
    m_norm: FloatArray
    ps_curvature: FloatArray
    ss_curvature: FloatArray


@dataclass
class BladeGeometry:
    camber: CamberGeometry
    surfaces: BladeSurfaceGeometry
    curvature: CurvatureGeometry
    metrics: BladeMetrics
    master_surfaces: BladeSurfaceGeometry
    thickness: FloatArray
    resolved_mapping: SurfaceMapping
    warnings: list[ValidationIssue] = field(default_factory=list)
