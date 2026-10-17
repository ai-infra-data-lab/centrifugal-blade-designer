import json
import numpy as np
import pytest
from tests.cad.conftest import sample_parameters,run_job
from blade_designer.models.parameters import TipClearanceParameters
from blade_designer.models.cad import MechanicalExportScope


@pytest.mark.parametrize('te,thin',[(2.,False),(3.,True)])
def test_clearanced_blade_only_cad_uses_tip_below_unmodified_casing(tmp_path,te,thin):
    p=sample_parameters();p.tip_clearance=TipClearanceParameters(2.,te)
    if thin:
        for section in p.sections:
            for point in section.thickness.points:point.value=1.
    p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    result=run_job(p,tmp_path/'clearance','mechanical')
    report=result['report']
    assert report['solid_validity']=='PASS'
    assert report['artifacts']['mechanical']['status']=='PASS'
    assert report['checks']['result']['solid_count']==1
    assert report['checks']['result']['volume_mm3']>0
    request=json.loads((result['job']/'request.json').read_text())
    np.testing.assert_allclose([point[0] for segment in request['shroud_segments'] for point in segment],80.,atol=1e-12)
    with np.load(result['job']/'geometry.npz') as data:
        assert np.max(data['main_2_ps'][:,2])<80.
        np.testing.assert_allclose(data['main_0_ps'][:,2],0.,atol=1e-12)
