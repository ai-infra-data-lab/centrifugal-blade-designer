"""Component topology, independent of GUI and external file formats."""
from dataclasses import dataclass, field
from enum import Enum

class StationType(str, Enum):
    INLET = "INLET"
    IMP_LE = "IMP_LE"
    IMP_TE = "IMP_TE"
    DIF_LE = "DIF_LE"
    DIF_TE = "DIF_TE"
    OUTLET = "OUTLET"

@dataclass
class ComponentStation:
    kind: StationType
    m_flow_norm: float

@dataclass
class FlowPathParameters:
    stations: list[ComponentStation] = field(default_factory=lambda: [
        ComponentStation(kind,value) for kind,value in zip(StationType,(0.,.15,.85,.90,.96,1.))])

    align_blade_stations_to_crossflow: bool = True

    def position(self,kind):
        return next(s.m_flow_norm for s in self.stations if s.kind == kind)

    def set_position(self,kind,value):
        next(s for s in self.stations if s.kind == kind).m_flow_norm = value

@dataclass(frozen=True)
class ComponentRegion:
    name: str
    start: float
    end: float
