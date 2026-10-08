"""Span correspondence uses segment-local topology, never closed-contour indices."""
from dataclasses import dataclass
import numpy as np

@dataclass
class SpanwiseLine:
    segment: str
    segment_fraction: float
    segment_index: int
    spans: np.ndarray
    xyz: np.ndarray

def build_spanwise_wireframe(sections):
    if len(sections)<2:raise ValueError("Wireframe requires at least Hub and Tip.")
    spans=np.array([section.span for section in sections],dtype=float)
    if not np.isfinite(spans).all() or spans[0]!=0 or spans[-1]!=1 or np.any(np.diff(spans)<=0):
        raise ValueError("Wireframe sections must increase from Hub to Tip.")
    lines=[]
    for name in ("le","ps","te","ss"):
        try:arrays=[getattr(section,name).xyz for section in sections]
        except (AttributeError,ValueError) as exc:raise ValueError(f"Wireframe topology missing segment {name.upper()}.") from exc
        count=len(arrays[0])
        if count<2 or any(a.shape!=(count,3) or not np.isfinite(a).all() for a in arrays):
            raise ValueError(f"Wireframe topology/index mismatch or invalid coordinates in {name.upper()}.")
        for index in range(count):
            lines.append(SpanwiseLine(name.upper(),index/(count-1),index,spans.copy(),
                np.array([a[index] for a in arrays],dtype=np.float64)))
    return lines
