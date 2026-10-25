"""Bounded buried-cap refinement for provisional disk construction only."""
from math import isfinite
from .errors import BooleanUnionError

ROOT_CAP_NOT_BURIED = 'Buried root construction cap is not wholly inside the Hub solid.'


def refine_provisional_root(backend, sections, blade, hub, tolerance_mm, *, enabled=False):
    """Keep the original Span surface; vary only its buried continuation.

    Arbitrary user-defined disks keep their existing construction path. No
    radius, disk dimensions, tolerance or containment predicate is relaxed.
    """
    if not enabled:
        return blade, []
    depth=blade.metrics.get('root_extension_reference_mm',0.)
    fraction=blade.metrics.get('root_extension_span_fraction',0.)
    if (not isfinite(depth) or not isfinite(fraction) or depth<=0 or not 0<fraction<=.1):
        raise BooleanUnionError('Invalid provisional root continuation metadata.')
    attempts=[];current=blade
    for index in range(4):
        try:
            if backend.check_buried_root_caps(current,hub) is not True:
                raise BooleanUnionError('Provisional root cap containment was not confirmed.')
            attempts.append({'depth_mm':depth,'span_fraction':fraction,'cap_inside_hub':True})
            return current,attempts
        except BooleanUnionError as error:
            attempts.append({'depth_mm':depth,'span_fraction':fraction,'cap_inside_hub':False,'error':str(error)})
            if str(error)!=ROOT_CAP_NOT_BURIED or index==3 or 2*fraction>.1:
                raise
            depth*=2;fraction*=2
            current=backend.create_blade_solid(sections,tolerance_mm,root_extension_mm=depth)
    raise AssertionError('Unreachable root construction state.')
