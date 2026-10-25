from copy import deepcopy
from types import SimpleNamespace
import pytest
from blade_designer.cad.root_construction import refine_provisional_root,ROOT_CAP_NOT_BURIED
from blade_designer.cad.errors import BooleanUnionError


def blade(depth=.2,fraction=.02):
    return SimpleNamespace(metrics={'root_extension_reference_mm':depth,'root_extension_span_fraction':fraction})


class Backend:
    def __init__(self,depth=.4,error=ROOT_CAP_NOT_BURIED):
        self.required=depth;self.error=error;self.calls=[]
    def check_buried_root_caps(self,model,hub):
        if model.metrics['root_extension_reference_mm']<self.required:raise BooleanUnionError(self.error)
        return True
    def create_blade_solid(self,sections,tolerance_mm,root_extension_mm):
        self.calls.append((sections,tolerance_mm,root_extension_mm))
        return blade(root_extension_mm,root_extension_mm/10)


def test_provisional_refinement_preserves_inputs_and_requires_actual_containment():
    backend=Backend();original=blade();before=deepcopy(original.metrics);sections=[{'span':0},{'span':1}]
    result,attempts=refine_provisional_root(backend,sections,original,object(),.01,enabled=True)
    assert result.metrics['root_extension_reference_mm']==.4
    assert [attempt['cap_inside_hub'] for attempt in attempts]==[False,True]
    assert backend.calls==[(sections,.01,.4)] and backend.calls[0][0] is sections
    assert original.metrics==before


def test_user_defined_disk_never_automatically_changes_continuation():
    backend=Backend();original=blade()
    result,attempts=refine_provisional_root(backend,[],original,object(),.01)
    assert result is original and not attempts and not backend.calls


def test_already_buried_provisional_cap_is_unchanged():
    backend=Backend(depth=.1);original=blade()
    result,attempts=refine_provisional_root(backend,[],original,object(),.01,enabled=True)
    assert result is original and len(attempts)==1 and not backend.calls


def test_refinement_does_not_exceed_span_bound_or_hide_unburied_cap():
    backend=Backend(depth=10.)
    with pytest.raises(BooleanUnionError,match='not wholly inside'):
        refine_provisional_root(backend,[],blade(),object(),.01,enabled=True)
    assert [call[2] for call in backend.calls]==[.4,.8]


def test_other_geometry_errors_are_not_retried_or_suppressed():
    backend=Backend(error='Missing construction root cap in blade topology.')
    with pytest.raises(BooleanUnionError,match='Missing construction root cap'):
        refine_provisional_root(backend,[],blade(),object(),.01,enabled=True)
    assert not backend.calls
