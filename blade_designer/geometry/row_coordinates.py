"""Display coordinates: each owned meridional row occupies one integer interval.

Physical distance follows the wall's inlet-to-outlet chain, including inward
Return Channels. No Qt, serialization, shape changes or inferred ownership.
"""
from dataclasses import dataclass
from numbers import Real
import numpy as np
from ..models.meridional import LineSegmentParameters, ArcSegmentParameters


@dataclass(frozen=True)
class RowCoordinates:
    order: tuple
    boundaries: dict
    intervals: dict
    owners: dict

    def position(self,identifier,wall,fraction):
        if (isinstance(fraction,(bool,np.bool_)) or not isinstance(fraction,Real)
                or not np.isfinite(fraction) or not 0<=fraction<=1):
            raise ValueError('Wall distance must be a finite normalized value in [0, 1].')
        start,end=self.intervals[wall][identifier]
        return self.order.index(identifier)+(fraction*self.boundaries[wall][-1]-start)/(end-start)

    def segment_interval(self,wall,index):
        identifier=self.owners[wall][index]
        if identifier is None:return None
        start,end=self.intervals[wall][identifier];offset=self.order.index(identifier)
        return tuple(offset+(v-start)/(end-start) for v in self.boundaries[wall][index:index+2])


def build_row_coordinates(curves,identifiers):
    """Require one continuous owned run per row and matching Hub/Shroud order.

    Unowned gaps have no coordinate; do not stretch a neighbor through a gap.
    An unassigned/disconnected row makes this derived display unavailable only.
    """
    identifiers=tuple(identifiers)
    if not identifiers or len(set(identifiers))!=len(identifiers):
        raise ValueError('翼列を登録し、Hub/Shroud区間の所属翼列を設定してください。')
    if len(curves)!=2:raise ValueError('Hub and Shroud definitions are required.')
    boundaries={};intervals={};owners={};orders=[]
    for wall,curve in zip(('hub','shroud'),curves):
        lengths=[];labels=[]
        for segment in curve.segments:
            if isinstance(segment,LineSegmentParameters):length=segment.length
            elif isinstance(segment,ArcSegmentParameters):
                if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,Real) or not np.isfinite(v) for v in (segment.radius,segment.sweep_deg)) or segment.radius<=0:
                    raise ValueError('Invalid meridional arc radius/sweep.')
                length=segment.radius*abs(np.deg2rad(segment.sweep_deg))
            else:raise ValueError('Unknown meridional segment type.')
            if isinstance(length,(bool,np.bool_)) or not isinstance(length,Real) or not np.isfinite(length) or length<=0:
                raise ValueError('Meridional segment lengths must be positive and finite.')
            if segment.blade_row is not None and segment.blade_row not in identifiers:
                raise ValueError('所属翼列が登録された翼列と一致しません。')
            lengths.append(length);labels.append(segment.blade_row)
        bounds=np.r_[0.,np.cumsum(lengths)]
        if not np.isfinite(bounds).all():raise ValueError('Non-finite meridional distance.')
        spans={}
        for identifier in identifiers:
            ids=[i for i,label in enumerate(labels) if label==identifier]
            if not ids:raise ValueError('全翼列にHubとShroudの所属区間を設定してください。')
            if ids!=list(range(ids[0],ids[-1]+1)):
                raise ValueError('各翼列の所属区間は各壁面で連続させてください。')
            start,end=float(bounds[ids[0]]),float(bounds[ids[-1]+1])
            if end<=start:raise ValueError('Row interval has no resolvable physical length.')
            spans[identifier]=(start,end)
        orders.append(tuple(sorted(identifiers,key=lambda key:spans[key][0])))
        boundaries[wall]=bounds;intervals[wall]=spans;owners[wall]=tuple(labels)
    if orders[0]!=orders[1]:raise ValueError('HubとShroudで入口からの翼列順序を一致させてください。')
    return RowCoordinates(orders[0],boundaries,intervals,owners)
