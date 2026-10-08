"""Blade endpoints on each wall, independent of component boundaries."""
from dataclasses import dataclass,field

@dataclass
class BladeEdgePosition:
    hub_m_flow_norm: float
    shroud_m_flow_norm: float

@dataclass
class BladeRowEdgeParameters:
    leading_edge: BladeEdgePosition = field(default_factory=lambda:BladeEdgePosition(.15,.15))
    trailing_edge: BladeEdgePosition = field(default_factory=lambda:BladeEdgePosition(.85,.85))
    # Independent correspondence knots; legacy migration preserves its sampling grid.
    reference_le_fraction: float = .15
    reference_te_fraction: float = .85
    legacy_uniform_sampling: bool = False

def default_diffuser_edges():
    return BladeRowEdgeParameters(BladeEdgePosition(.90,.90),BladeEdgePosition(.96,.96),.90,.96)
