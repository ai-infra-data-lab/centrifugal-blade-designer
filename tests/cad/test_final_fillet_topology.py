"""History-only faces must never become final fillet radius evidence."""
import pytest
from .test_root_interface_reconciliation import native_json


@pytest.mark.parametrize('history_only',[False,True])
def test_fillet_history_is_restricted_to_final_topology(tmp_path,history_only):
    report=native_json(tmp_path, '''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP import BRepFilletAPI
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeSphere
from OCP.TopAbs import TopAbs_FACE,TopAbs_EDGE
from blade_designer.cad.occt_backend import OcctBackend,CadShape,shapes
from blade_designer.cad.cad_validation import fillet_samples,require_fillet_samples
native=BRepFilletAPI.BRepFilletAPI_MakeFillet
phantom=shapes(BRepPrimAPI_MakeSphere(.003).Shape(),TopAbs_FACE)[0]
history_only=HISTORY_ONLY
class HistoryWithConstructionFace:
 def __init__(self,shape):self.actual=native(shape)
 def __getattr__(self,name):return getattr(self.actual,name)
 def NewFaces(self,index):
  return [phantom] if history_only else [*self.actual.NewFaces(index),phantom]
 def Generated(self,shape):return [*self.actual.Generated(shape),phantom]
BRepFilletAPI.BRepFilletAPI_MakeFillet=HistoryWithConstructionFace
shape=BRepPrimAPI_MakeBox(5,5,5).Shape();backend=OcctBackend()
from blade_designer.cad.errors import FilletGenerationError
try:result=backend.apply_fillet(CadShape(shape),[shapes(shape,TopAbs_EDGE)[0]],.1)
except FilletGenerationError as exc:
 assert history_only
 print(json.dumps({'error':str(exc)}))
else:
 assert not history_only
 actual=shapes(result.shape,TopAbs_FACE)
 assert all(any(face.IsSame(old) for old in actual) for face in result.labels['HUB_FILLET'])
 assert not any(face.IsSame(phantom) for face in result.labels['HUB_FILLET'])
 measurement=fillet_samples(result,.1);require_fillet_samples(measurement)
 print(json.dumps({'excluded':result.metrics['excluded_intermediate_fillet_faces'],
                   'rolling':len(measurement['faces']),'solid':backend.validate_solid(result)['solid_count']}))
'''.replace('HISTORY_ONLY',repr(history_only)))
    if history_only:
        assert 'no generated root fillet faces' in report['error']
    else:
        assert report['excluded']==1 and report['rolling']>0 and report['solid']==1
