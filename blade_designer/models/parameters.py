from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy
from .blade_edge import BladeEdgePosition,BladeRowEdgeParameters,default_diffuser_edges
from .resolution import GeometryResolutionParameters
from .cad import CadExportParameters
from .flow_path import FlowPathParameters, StationType
from .meridional import MeridionalCurveParameters, default_shroud


class RotationDirection(str, Enum):
    CCW = "ccw"
    CW = "cw"

    @property
    def sign(self):return 1 if self is RotationDirection.CCW else -1


class EdgeType(str, Enum):
    CIRCULAR = "circular"
    ELLIPTICAL = "elliptical"
    CUTOFF = "cutoff"


class SurfaceMapping(str, Enum):
    AUTO = "auto"
    POSITIVE_IS_PS = "positive_is_ps"
    NEGATIVE_IS_PS = "negative_is_ps"


@dataclass
class GeometryParameters:
    r_le: float = 100.0
    r_te: float = 160.0
    theta_le_deg: float = 0.0
    vane_count: int = 20


@dataclass(init=False)
class DistributionPoint:
    m_blade_norm: float
    value: float

    def __init__(self,m_blade_norm=None,value=0.,*,m_norm=None):
        if m_blade_norm is not None and m_norm is not None:
            raise ValueError("Specify only m_blade_norm; m_norm is a legacy alias.")
        self.m_blade_norm=m_norm if m_blade_norm is None else m_blade_norm
        self.value=value

    @property
    def m_norm(self):return self.m_blade_norm

    @m_norm.setter
    def m_norm(self,value):self.m_blade_norm=value


ControlPoint = DistributionPoint


@dataclass
class BladeAngleParameters:
    points: list[DistributionPoint] = field(default_factory=lambda: [
        DistributionPoint(m, b) for m, b in zip([0., .25, .5, .75, 1.], [65., 62., 58., 54., 50.])
    ])


@dataclass
class ThicknessParameters:
    points: list[DistributionPoint] = field(default_factory=lambda: [
        DistributionPoint(0., 1.), DistributionPoint(.35, 4.), DistributionPoint(1., 1.)
    ])


@dataclass
class EdgeParameters:
    le_type: EdgeType = EdgeType.CIRCULAR
    le_ellipse_ratio: float = 1.0
    te_type: EdgeType = EdgeType.CIRCULAR
    te_ellipse_ratio: float = 1.0


@dataclass
class OutputPointParameters:
    le_points: int = 21
    ps_points: int = 101
    te_points: int = 21
    ss_points: int = 101


@dataclass
class ExportParameters:
    significant_digits: int = 6
    repeat_first_point: bool = False


@dataclass
class BladeSection:
    span: float
    blade_angle: BladeAngleParameters = field(default_factory=BladeAngleParameters)
    thickness: ThicknessParameters = field(default_factory=ThicknessParameters)
    edge_parameters: EdgeParameters = field(default_factory=EdgeParameters)


@dataclass
class TurboGridParameters:
    geometry_unit: str = "MM"
    rotation_axis: str = "Z"
    hub_curve_filename: str = "hub.curve"
    shroud_curve_filename: str = "shroud.curve"
    profile_curve_filename: str = "profile.curve"
    leading_edge_type: str = "auto"
    trailing_edge_type: str = "auto"


@dataclass
class SplitterParameters:
    hub_start_fraction: float = 0.5
    tip_start_fraction: float = 0.5
    pitch_fraction: float = 0.5
    thickness_scale: float = 1.0
    sections: list[BladeSection] | None = None


@dataclass
class TipClearanceParameters:
    le_mm: float = 0.0
    te_mm: float = 0.0


@dataclass
class ImpellerTrimParameters:
    """Derivative settings; source walls and blade distributions remain intact."""
    shroud_area_cut_percent: float = 0.0
    diameter_mode: str = "off"
    diameter_mm: float = 0.0
    diameter_cut_percent: float = 0.0


@dataclass
class BladeParameters:
    geometry: GeometryParameters = field(default_factory=GeometryParameters)
    blade_angle: BladeAngleParameters = field(default_factory=BladeAngleParameters)
    thickness: ThicknessParameters = field(default_factory=ThicknessParameters)
    edges: EdgeParameters = field(default_factory=EdgeParameters)
    output_points: OutputPointParameters = field(default_factory=OutputPointParameters)
    export: ExportParameters = field(default_factory=ExportParameters)
    rotation_direction: RotationDirection = RotationDirection.CCW
    surface_mapping: SurfaceMapping = SurfaceMapping.AUTO
    hub: MeridionalCurveParameters = field(default_factory=MeridionalCurveParameters)
    shroud: MeridionalCurveParameters = field(default_factory=default_shroud)

    sections: list[BladeSection] | None = None
    diffuser_profile: BladeSection | None = None
    turbogrid: TurboGridParameters = field(default_factory=TurboGridParameters)
    blade_le_fraction: float = 0.15
    blade_te_fraction: float = 0.85

    impeller_edges: BladeRowEdgeParameters = field(default_factory=BladeRowEdgeParameters)
    diffuser_edges: BladeRowEdgeParameters = field(default_factory=default_diffuser_edges)
    flow_path: FlowPathParameters | None = None
    resolution: GeometryResolutionParameters = field(default_factory=GeometryResolutionParameters)
    blade_rows: list[BladeRow] | None = None
    active_blade_row: str | None = None
    impeller_te_rake_deg: float | None = None
    splitter: SplitterParameters | None = None
    tip_clearance: TipClearanceParameters | None = None
    impeller_trim: ImpellerTrimParameters | None = None
    cad_export: CadExportParameters = field(default_factory=CadExportParameters)

    def __post_init__(self):
        if self.flow_path is None:
            self.flow_path = FlowPathParameters()
            self.flow_path.set_position(StationType.IMP_LE,self.__dict__["blade_le_fraction"])
            self.flow_path.set_position(StationType.IMP_TE,self.__dict__["blade_te_fraction"])
        if self.sections is None:
            # Legacy diffuser fields alias Hub; mutations remain backward compatible.
            self.sections = [BladeSection(0.,self.blade_angle,self.thickness,self.edges),
                             BladeSection(1.,deepcopy(self.blade_angle),deepcopy(self.thickness),deepcopy(self.edges))]
        if self.diffuser_profile is None:
            self.diffuser_profile=deepcopy(self.sections[0]);self.diffuser_profile.span=0.

    def __getattribute__(self,name):
        # Keep the v0.2 constructor/API and dataclass JSON fields, with Hub as
        # the single source of truth even if an entire distribution is replaced.
        stations={"blade_le_fraction":StationType.IMP_LE,"blade_te_fraction":StationType.IMP_TE}
        if name in stations:
            flow=object.__getattribute__(self,"__dict__").get("flow_path")
            if flow is not None:return flow.position(stations[name])
        aliases={"blade_angle":"blade_angle","thickness":"thickness","edges":"edge_parameters"}
        if name in aliases:
            sections=object.__getattribute__(self,"__dict__").get("sections")
            if sections:return getattr(sections[0],aliases[name])
        return object.__getattribute__(self,name)

    def __setattr__(self,name,value):
        stations={"blade_le_fraction":StationType.IMP_LE,"blade_te_fraction":StationType.IMP_TE}
        flow=self.__dict__.get("flow_path")
        if name in stations and flow is not None:flow.set_position(stations[name],value)
        aliases={"blade_angle":"blade_angle","thickness":"thickness","edges":"edge_parameters"}
        if name in aliases:
            sections=self.__dict__.get("sections")
            if sections:setattr(sections[0],aliases[name],value)
        object.__setattr__(self,name,value)


@dataclass
class BladeRow:
    identifier: str
    name: str
    kind: str
    parameters: BladeParameters
