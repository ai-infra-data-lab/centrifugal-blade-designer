from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from numpy.typing import NDArray
FloatArray = NDArray[np.float64]


@dataclass
class SampledWallCurve:
    z: FloatArray
    r: FloatArray


class SegmentType(str, Enum):
    LINE = "line"
    ARC = "arc"


@dataclass
class LineSegmentParameters:
    length: float = 25.0
    blade_row: str | None = None


@dataclass
class ArcSegmentParameters:
    radius: float = 20.0
    sweep_deg: float = 35.0
    clockwise: bool = False
    blade_row: str | None = None


@dataclass
class MeridionalCurveParameters:
    start_z: float = 0.0
    start_r: float = 50.0
    start_angle_deg: float = 0.0
    segments: list[LineSegmentParameters | ArcSegmentParameters] = field(default_factory=lambda: [
        LineSegmentParameters(25), ArcSegmentParameters(30,90), LineSegmentParameters(55)])
    export_points: int = 501


@dataclass
class Point2D:
    z: float
    r: float

    @property
    def zr(self) -> FloatArray:
        return np.array([self.z,self.r],dtype=np.float64)


@dataclass
class LineSegmentGeometry:
    start: Point2D
    end: Point2D
    start_tangent: FloatArray
    end_tangent: FloatArray
    length: float


@dataclass
class ArcSegmentGeometry(LineSegmentGeometry):
    center: Point2D
    radius: float
    sweep_rad: float
    clockwise: bool


@dataclass
class MeridionalGeometry:
    segments: list[LineSegmentGeometry | ArcSegmentGeometry]
    z: FloatArray
    r: FloatArray
    m: FloatArray

    @property
    def length(self) -> float:
        return sum(s.length for s in self.segments)


def default_shroud() -> MeridionalCurveParameters:
    # Parallel inlet/outlet, concentric turn, finite passage width throughout.
    return MeridionalCurveParameters(0,65,0,[LineSegmentParameters(25),
        ArcSegmentParameters(15,90),LineSegmentParameters(55)])
