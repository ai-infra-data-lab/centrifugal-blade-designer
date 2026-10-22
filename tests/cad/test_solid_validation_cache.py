"""Native checks remain mandatory after mutation and for imported objects."""
import pytest
from .test_root_interface_reconciliation import native_json


SETUP='''
import sys,json,gc,weakref
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS
from OCP.TopAbs import TopAbs_EDGE
from blade_designer.cad.occt_backend import OcctBackend,CadShape,shapes
from blade_designer.cad.errors import InvalidSolidError
backend=OcctBackend();calls=[];native=backend._validate_solid_uncached
def counted(model):
 calls.append(id(model));return native(model)
backend._validate_solid_uncached=counted
def box():return CadShape(BRepPrimAPI_MakeBox(5,5,5).Shape())
model=box()
'''


CASES={
    'same_object_and_fresh_import': '''
first=backend.validate_solid(model);first['bbox_mm'][0]=999
second=backend.validate_solid(model)
assert len(calls)==1 and second['bbox_mm'][0]!=999
backend.validate_solid(CadShape(model.shape))
assert len(calls)==2
assert not OcctBackend()._solid_validation_cache
''',
    'tolerance_orientation_and_one_ulp': '''
backend.validate_solid(model)
edge=TopoDS.Edge(shapes(model.shape,TopAbs_EDGE)[0]);BRep_Builder().UpdateEdge(edge,.02)
assert backend.validate_solid(model)['max_edge_tolerance_mm']==.02 and len(calls)==2
model.shape.Reverse()
for _ in range(2):
 try:backend.validate_solid(model)
 except InvalidSolidError:pass
 else:raise AssertionError('Invalid reversed solid was cached')
assert len(calls)==4
model.shape.Reverse();backend.validate_solid(model);assert len(calls)==4
first=box();before=backend._solid_fingerprint(first.shape)
first.shape=BRepPrimAPI_MakeBox(float(np.nextafter(5.,6.)),5,5).Shape()
assert backend._solid_fingerprint(first.shape)!=before
model.shape=first.shape;backend.validate_solid(model);assert len(calls)==5
''',
    'bounded_and_weak': '''
models=[box() for _ in range(12)]
for item in models:backend.validate_solid(item)
assert len(backend._solid_validation_cache)==8
backend.validate_solid(models[0]);assert len(calls)==13
reference=weakref.ref(models[-1]);del item;models.clear();gc.collect()
assert reference() is None
''',
    'fingerprint_failure_never_bypasses_native': '''
def unavailable(shape):raise RuntimeError('Injected serialization failure')
backend._solid_fingerprint=unavailable
backend.validate_solid(model);backend.validate_solid(model)
assert len(calls)==2 and not backend._solid_validation_cache
model.shape.Reverse()
try:backend.validate_solid(model)
except InvalidSolidError:pass
else:raise AssertionError('Serialization failure bypassed validation')
''',
    'native_mutation_is_not_cached': '''
def changing(candidate):
 result=counted(candidate)
 if len(calls)==1:
  edge=TopoDS.Edge(shapes(candidate.shape,TopAbs_EDGE)[0]);BRep_Builder().UpdateEdge(edge,.04)
 return result
backend._validate_solid_uncached=changing
backend.validate_solid(model);assert not backend._solid_validation_cache
assert backend.validate_solid(model)['max_edge_tolerance_mm']==.04
backend.validate_solid(model);assert len(calls)==2
''',
    'non_weak_object_is_validated_without_reuse': '''
class Wrapper:
 __slots__=('shape',)
candidate=Wrapper();candidate.shape=model.shape
backend.validate_solid(candidate);backend.validate_solid(candidate)
assert len(calls)==2 and not backend._solid_validation_cache
''',
}


@pytest.mark.parametrize('case',CASES)
def test_native_validation_cache_contract(tmp_path,case):
    result=native_json(tmp_path,SETUP+CASES[case]+"\nprint(json.dumps({'case':"+repr(case)+",'native_checks':len(calls)}))")
    assert result['case']==case and result['native_checks']>=1
