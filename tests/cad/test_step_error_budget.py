import pytest
from blade_designer.cad.cad_validation import step_roundtrip
from blade_designer.cad.errors import CadExportError


class MeasuredBackend:
    """Unit-test only: exercise comparison policy, not CAD generation."""
    def __init__(self,shift=.0003,edge=.0002,volume=1.):
        self.shift=shift;self.edge=edge;self.volume=volume
    def read_step(self,path):return 'imported'
    def validate_solid(self,model):
        imported=model=='imported'
        return {'solid_count':1,'volume_mm3':self.volume if imported else 1.,
            'surface_area_mm2':10.,'max_edge_tolerance_mm':self.edge,
            'bbox_mm':[self.shift if imported else 0.,0.,0.,1.,1.,1.]}


def test_step_bbox_uses_measured_brep_budget(tmp_path):
    path=tmp_path/'measured.step';path.write_text('SI_UNIT(.MILLI.,.METRE.)')
    result,_=step_roundtrip(MeasuredBackend(),'source',path,.01)
    assert result['bbox_tolerance_mm']==.0004
    assert result['volume_tolerance_mm3']==.001


@pytest.mark.parametrize('options',[{'shift':.001},{'edge':.02},{'volume':1.01}])
def test_step_budget_does_not_accept_excess_bbox_gap_or_volume(tmp_path,options):
    path=tmp_path/'invalid.step';path.write_text('SI_UNIT(.MILLI.,.METRE.)')
    with pytest.raises(CadExportError):step_roundtrip(MeasuredBackend(**options),'source',path,.01)
