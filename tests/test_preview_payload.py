"""Internal transfer integrity; no project or export schema is changed."""
from copy import deepcopy
import json
import numpy as np
import pytest

from blade_designer.fileio import preview_payload as codec
from blade_designer.geometry.preview_computation import prepare_preview, prepare_row_previews
from blade_designer.models.parameters import BladeParameters, TipClearanceParameters, ImpellerTrimParameters, SplitterParameters
from blade_designer.models.validation import ValidationIssue,ValidationLevel
from test_preview_computation import assert_exact


@pytest.mark.parametrize("variant",["base","clearance","trim","splitter"])
def test_actual_results_roundtrip_exactly_with_provenance(variant):
    params=BladeParameters()
    if variant=="clearance":params.tip_clearance=TipClearanceParameters(.5,1.,.2,.3)
    if variant=="trim":params.impeller_trim=ImpellerTrimParameters(10)
    if variant=="splitter":params.splitter=SplitterParameters()
    before=deepcopy(params)
    result=(prepare_preview(params,"impeller",include_legacy=True),prepare_row_previews(params))
    assert result[0].selected_error is None
    restored=codec.loads(codec.dumps(result))
    assert_exact(restored,result)
    assert params==before


def test_aliases_enums_empty_arrays_noncontiguous_and_numpy_scalars():
    array=np.arange(18,dtype=np.float64).reshape(3,6)[:,::2]
    values=[array,array,np.empty((0,3)),np.float64(1.25),np.float64(2.75),np.int64(17),
            ValidationIssue(ValidationLevel.WARNING,"field","message"),float('nan'),float('inf')]
    restored=codec.loads(codec.dumps(values))
    assert restored[0] is restored[1]
    np.testing.assert_array_equal(restored[0],array)
    assert restored[2].shape==(0,3) and restored[2].dtype==np.float64
    assert restored[3:6]==[1.25,2.75,17] and isinstance(restored[3],np.float64)
    assert restored[6]==values[6] and np.isnan(restored[7]) and np.isinf(restored[8])


@pytest.mark.parametrize("value",[object(),np.array([object()],dtype=object),np.array([1+2j])])
def test_executable_or_non_numerical_payloads_are_not_serialized(value):
    with pytest.raises(ValueError):codec.dumps(value)


@pytest.mark.parametrize("damage",["dtype","shape","truncated","base64","class","ref","cycle","fields","version"])
def test_malformed_payloads_are_rejected(damage):
    doc=json.loads(codec.dumps([np.arange(3.),ValidationIssue(ValidationLevel.WARNING,"f","m")]))
    array=next(n for n in doc['nodes'] if n['type']=='array')
    obj=next(n for n in doc['nodes'] if n['type']=='dataclass')
    if damage=='dtype':array['dtype']='O'
    if damage=='shape':array['shape']=[10**12]
    if damage=='truncated':array['data']=array['data'][:-4]
    if damage=='base64':array['data']='!'*len(array['data'])
    if damage=='class':obj['class']='os.system'
    if damage=='ref':doc['root']={'ref':-1}
    if damage=='cycle':doc['nodes'][0]['items']=[{'ref':0}]
    if damage=='fields':obj['fields']['unexpected']=1
    if damage=='version':doc['version']=9
    with pytest.raises(ValueError):codec.loads(json.dumps(doc).encode())


def test_size_limit_applies_before_decoding_or_allocating(monkeypatch):
    monkeypatch.setattr(codec,'MAX_BYTES',10)
    with pytest.raises(ValueError,match='limit'):codec.loads(b' '*11)
    with pytest.raises(ValueError,match='limit'):codec.dumps(np.ones(2))
