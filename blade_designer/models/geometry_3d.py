from dataclasses import dataclass
import numpy as np
from .geometry import FloatArray
from .meridional import MeridionalGeometry


@dataclass
class Curve3D:
    r: FloatArray
    theta_rad: FloatArray
    z: FloatArray
    m_blade_norm: FloatArray | None = None
    meridional_distance: FloatArray | None = None
    source_span: FloatArray | None = None

    @property
    def m_norm(self):return self.m_blade_norm

    @m_norm.setter
    def m_norm(self,value):self.m_blade_norm=value

    @property
    def x(self): return self.r*np.cos(self.theta_rad)
    @property
    def y(self): return self.r*np.sin(self.theta_rad)
    @property
    def xyz(self): return np.column_stack((self.x,self.y,self.z))


@dataclass
class SectionGeometry3D:
    span: float
    camber: Curve3D
    ps: Curve3D
    ss: Curve3D
    le: Curve3D
    te: Curve3D
    master_ps: Curve3D
    master_ss: Curve3D
    master_le: Curve3D
    master_te: Curve3D
    m: FloatArray
    beta_m_deg: FloatArray
    thickness: FloatArray


@dataclass
class TipMeridionalGeometry:
    """Derived sampled Tip; casing_m retains the unmodified casing reference."""
    casing_m: FloatArray
    z: FloatArray
    r: FloatArray
    clearance_mm: FloatArray
    le_casing_m: float
    te_casing_m: float


@dataclass
class ImpellerGeometry:
    hub: MeridionalGeometry
    shroud: MeridionalGeometry
    sections: list[SectionGeometry3D]
    splitter_sections: list[SectionGeometry3D] | None = None
    tip: TipMeridionalGeometry | None = None
    source_geometry: "ImpellerGeometry | None" = None
    trim_report: dict | None = None
