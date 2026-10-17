"""Read-only geometric passage measurements (mm, mm²)."""
from dataclasses import dataclass, field
import numpy as np


@dataclass(frozen=True)
class PassageAreaStation:
    m_flow_norm: float
    gross_annulus: float
    main_reference: float
    net_per_pitch: float
    main_splitter: float | None
    splitter_main: float | None
    tip_gap_per_pitch: float = 0.0


@dataclass(frozen=True)
class PassageThroat:
    name: str
    spans: np.ndarray
    widths: np.ndarray
    first_xyz: np.ndarray
    second_xyz: np.ndarray
    strip_area: float
    reference_only: bool = False
    method: str = "Section chord estimate"

    @property
    def minimum_width(self):
        return float(np.min(self.widths))


@dataclass
class PassageResult:
    vane_count: int
    stations: list[PassageAreaStation] = field(default_factory=list)
    throats: list[PassageThroat] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
