from dataclasses import dataclass,field

@dataclass(frozen=True)
class FlowAreaStation:
    m_flow_norm: float
    m: float
    z_mean: float
    r_mean: float
    hub_z: float
    hub_r: float
    shroud_z: float
    shroud_r: float
    passage_length: float
    gross_area: float
    component_region: str

@dataclass
class FlowAreaResult:
    stations: list[FlowAreaStation]
    named_stations: dict[str,FlowAreaStation|None]
    errors: list[str] = field(default_factory=list)

    @property
    def imp_le_area(self):
        reference=self.named_stations["IMP_LE"]
        return None if reference is None else reference.gross_area

    def area_ratio(self,station):
        return None if self.imp_le_area is None else station.gross_area/self.imp_le_area
