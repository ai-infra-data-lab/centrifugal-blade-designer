"""Full-wheel construction guards and actual default geometry, without ANSYS."""
import json
import subprocess
from copy import deepcopy
from pathlib import Path

from blade_designer.cad.client import ROOT,backend_python,prepare_job
from blade_designer.fileio.project_io import load_project
from blade_designer.geometry.provisional_disk import make_provisional_disk
from blade_designer.models.blade_rows import row_parameters
from blade_designer.models.cad import MechanicalExportScope
from .test_root_interface_reconciliation import native_json


SETUP='''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from blade_designer.cad.occt_backend import OcctBackend,CadShape,shapes
from blade_designer.cad.errors import BooleanUnionError,InvalidSolidError
backend=OcctBackend()
def box(x=0):return BRepPrimAPI_MakeBox(gp_Pnt(x,0,0),1,1,1).Shape()
'''


def test_bounds_are_only_a_lower_bound_and_original_sides_are_checked(tmp_path):
    result=native_json(tmp_path,SETUP+'''
a=shapes(box(),TopAbs_FACE);b=shapes(box(4),TopAbs_FACE)
model=CadShape(box(),{'HUB_FILLET_GROUP_a':a,'BLADE_GROUP_a':a,
 'HUB_FILLET_GROUP_b':b,'BLADE_GROUP_b':b},{'fillet_groups':{'a':{},'b':{}}})
bounded=backend.check_root_group_separation(model,.01,use_bounds=True,include_original_pairs=True)
exact=backend.check_root_group_separation(model,.01,include_original_pairs=True)
assert len(bounded)==len(exact)==4
for lower,actual in zip(bounded,exact):
 assert 0<lower['surface_distance_lower_bound_mm']<=actual['surface_distance_mm']==3
# Blends remain distant, but the original surfaces meet: fourth comparison
# must reject even though all three historical blend comparisons pass.
labels={'HUB_FILLET_GROUP_a':shapes(box(10),TopAbs_FACE),'BLADE_GROUP_a':a,
 'HUB_FILLET_GROUP_b':shapes(box(20),TopAbs_FACE),'BLADE_GROUP_b':a}
model.labels=labels
assert len(backend.check_root_group_separation(model,.01,use_bounds=True))==3
try:backend.check_root_group_separation(model,.01,use_bounds=True,include_original_pairs=True)
except InvalidSolidError:pass
else:raise AssertionError('Touching original surfaces accepted')
model.labels['BLADE_GROUP_b']=[]
try:backend.check_root_group_separation(model,.01,use_bounds=True,include_original_pairs=True)
except InvalidSolidError:pass
else:raise AssertionError('Missing side accepted')
for tolerance in (0.,-1.,float('nan'),float('inf')):
 try:backend.check_root_group_separation(model,tolerance,use_bounds=True)
 except InvalidSolidError:pass
 else:raise AssertionError('Invalid separation tolerance accepted')
print(json.dumps(bounded))
''')
    assert len(result)==4


def test_missing_stale_and_exposed_caps_rejected_without_mutating_sources(tmp_path):
    result=native_json(tmp_path,SETUP+'''
hub=CadShape(BRepPrimAPI_MakeBox(10,10,10).Shape())
shape=BRepPrimAPI_MakeBox(gp_Pnt(2,2,2),1,1,1).Shape()
inside=CadShape(shape,{'BLADE_HUB_CAP':[shapes(shape,TopAbs_FACE)[0]]},
 {'root_extension_span_fraction':.01})
before=[backend._solid_fingerprint(item.shape) for item in (inside,hub)]
assert backend.check_buried_root_caps(inside,hub)
assert before==[backend._solid_fingerprint(item.shape) for item in (inside,hub)]
assert not backend.check_buried_root_caps(CadShape(shape),hub)
errors=[]
for caps in ([],[shapes(box(30),TopAbs_FACE)[0]]):
 try:backend.check_buried_root_caps(CadShape(shape,{'BLADE_HUB_CAP':caps},inside.metrics),hub)
 except BooleanUnionError as exc:errors.append(str(exc))
 else:raise AssertionError('Missing or stale cap accepted')
outside_shape=box(30)
try:backend.check_buried_root_caps(CadShape(outside_shape,
 {'BLADE_HUB_CAP':[shapes(outside_shape,TopAbs_FACE)[0]]},inside.metrics),hub)
except BooleanUnionError as exc:errors.append(str(exc))
else:raise AssertionError('Exposed cap accepted')
print(json.dumps(errors))
''')
    assert len(result)==3 and 'not wholly inside' in result[-1]


def test_full_assembly_rejects_invalid_settings_before_boolean(tmp_path):
    result=native_json(tmp_path,SETUP+'''
hub=CadShape(box());blade=CadShape(box())
cases=[([],2,.1,.01),([('main',blade),('main',blade)],2,.1,.01),
 ([('main',blade)],True,.1,.01),([('main',blade)],0,.1,.01),
 ([('main',blade)],2,float('nan'),.01),([('main',blade)],2,.1,0),
 ([('main',blade)],2,.1,.01)]
errors=[]
for blades,count,radius,tolerance in cases:
 try:backend.filleted_full_impeller(blades,hub,count,radius,tolerance)
 except BooleanUnionError as exc:errors.append(str(exc))
 else:raise AssertionError('Invalid construction accepted')
print(json.dumps(errors))
''')
    assert len(result)==7 and 'buried root continuation' in result[-1]


def test_parallel_checker_keeps_native_flags_and_rejects_intersecting_solids(tmp_path):
    result=native_json(tmp_path,SETUP+'''
from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
import blade_designer.cad.occt_backend as module
events=[]
class ObservedCheck:
 def __init__(self):self.native=BRepAlgoAPI_Check()
 def SetRunParallel(self,value):events.append(('parallel',value));self.native.SetRunParallel(value)
 def SetData(self,shape,small,self_intersection):
  events.append(('flags',small,self_intersection));self.native.SetData(shape,small,self_intersection)
 def Perform(self):events.append(('perform',));self.native.Perform()
 def IsValid(self):return self.native.IsValid()
module.BRepAlgoAPI_Check=ObservedCheck
assert backend.validate_solid(CadShape(box()))['self_intersection_free']
compound=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(compound)
builder.Add(compound,box());builder.Add(compound,box(.5))
serial=BRepAlgoAPI_Check(compound,False,True);assert not serial.IsValid()
try:backend.validate_solid(CadShape(compound))
except InvalidSolidError:pass
else:raise AssertionError('Intersecting solids accepted')
assert events==[('parallel',True),('flags',False,True),('perform',)]*2
print(json.dumps(events))
''')
    assert len(result)==6


def test_actual_default_full_wheel_small_radius_and_step(tmp_path):
    project=load_project(ROOT/'blade_designer/defaults/default_project.json')
    row=next(row for row in project.blade_rows if row.kind=='impeller')
    params=row_parameters(project,row)
    params.cad_export.disk=make_provisional_disk(params)
    params.cad_export.fillet.hub_radius_mm=.1
    params.cad_export.mechanical_scope=MechanicalExportScope.FULL_IMPELLER
    before=deepcopy(params)
    job=prepare_job(params,'mechanical',tmp_path/'job')
    # Full native self-intersection, STEP import and bidirectional samples are costly.
    # A longer bound changes no kernel flags, tolerance or acceptance criteria.
    with (job/'test_process.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(backend_python()),'-X','utf8','-m','blade_designer.cad.worker',
            str(job.resolve())],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:code=process.wait(timeout=3600)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,check=False)
            process.wait(timeout=30)
            raise
    assert code==0,(job/'test_process.log').read_text(encoding='utf-8')
    report=json.loads((job/'result.json').read_text(encoding='utf-8'))
    assert params==before
    assert report.get('fillet_status')=='PASS',report.get('error')
    full=report['checks']['full_impeller']
    assert full['full_assembly_method']=='raw_full_union_then_single_fillet'
    count=params.geometry.vane_count
    groups={name+'@'+str(index) for name in ('main','splitter') for index in range(count)}
    assert set(full['periodic_root_coverage'])==groups
    for item in full['periodic_root_coverage'].values():
        assert item['root_roles']==['LE','PS','SS','TE'] and item['cap_containment']=='PASS'
    assert full['self_intersection_free'] and full['solid_count']==1
    assert full['max_edge_tolerance_mm']<=params.cad_export.surface_tolerance_mm
    separation=full['full_root_group_separation']
    assert len(separation)==len(groups)*(len(groups)-1)//2*4
    assert all(item['status']=='PASS' and item.get('surface_distance_mm',
        item.get('surface_distance_lower_bound_mm'))>item['required_mm'] for item in separation)
    artifact=report['artifacts']['mechanical']
    assert artifact['status']=='PASS' and artifact['roundtrip']['status']=='PASS'
    boundary=artifact['roundtrip']['boundary_surface_samples']
    assert boundary['status']=='PASS_SAMPLED' and boundary['global_surface_error']=='NOT_TESTED'
    for direction in ('source_to_imported','imported_to_source'):
        measured=boundary[direction]
        assert measured['face_count']>=len(groups) and len(measured['faces'])==measured['face_count']
        assert measured['sample_count']>=measured['face_count']
    for key in ('original','imported'):
        assert artifact['roundtrip'][key]['self_intersection_free']
        assert artifact['roundtrip'][key]['solid_count']==1
    for key in ('fillet_before_step','fillet_after_step'):
        assert all(face['status']=='PASS' for face in artifact['roundtrip'][key]['faces'])
    assert report['mechanical_import']==report['mechanical_mesh']=='NOT_TESTED'
    assert Path(job/'outputs'/artifact['files'][0]).is_file()
    from blade_designer.cad.preview_cache import read_preview_cache
    cached=read_preview_cache(job)
    assert cached['snapshot_hash']==report['parameter_snapshot_hash']
    assert sum(len(rows) for rows in cached['triangles_full'].values())>0
