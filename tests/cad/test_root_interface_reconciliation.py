"""Native buried-root construction, preserved cavities and manifold guard."""
import json
import subprocess
from copy import deepcopy
from blade_designer.cad.client import backend_python,ROOT
from blade_designer.fileio.project_io import load_project
from blade_designer.models.blade_rows import row_parameters
from blade_designer.models.cad import MechanicalExportScope
from blade_designer.geometry.provisional_disk import make_provisional_disk
from .conftest import run_job,sample_parameters


def test_actual_default_small_fillet_and_step_without_tolerance_relaxation(tmp_path):
    project=load_project(ROOT/'blade_designer/defaults/default_project.json')
    row=next(row for row in project.blade_rows if row.kind=='impeller')
    params=row_parameters(project,row)
    params.cad_export.disk=make_provisional_disk(params)
    # Explicitly selected for this shape, never an automatic radius fallback.
    params.cad_export.fillet.hub_radius_mm=.1
    params.cad_export.mechanical_scope=MechanicalExportScope.BLADE_HUB
    before=deepcopy(params)
    result=run_job(params,tmp_path/'job','mechanical')['report']
    assert params==before
    assert result.get('fillet_status')=='PASS',result.get('error')
    assert result['checks']['root_extension_mm']['main']>0
    for entry in result['checks']['fillet'].values():
        assert entry['root_cap_inside_hub'] and entry['fillet_radius_mm']==.1
        assert entry['fillet_face_count']==entry['rolling_fillet_face_count']+entry['corner_fillet_face_count']
        assert entry['fillet_role_basis']=='kernel_new_surfaces_excluding_support_history_and_geometry'
    separation=result['checks']['root_group_surface_separation']
    assert len(separation)==3
    assert all(item['status']=='PASS' and item['surface_distance_mm']>item['required_mm'] for item in separation)
    artifact=result['artifacts']['mechanical']
    assert artifact['status']=='PASS' and artifact['roundtrip']['status']=='PASS'
    for key in ('original','imported'):
        assert artifact['roundtrip'][key]['max_edge_tolerance_mm']<=params.cad_export.surface_tolerance_mm
        assert artifact['roundtrip'][key]['solid_count']==1
    for key in ('fillet_before_step','fillet_after_step'):
        measurement=artifact['roundtrip'][key]
        assert measurement['requested_radius_mm']==.1 and measurement['faces']
        assert all(face['status']=='PASS' for face in measurement['faces'])


def native_json(tmp_path,script):
    path=tmp_path/'native_check.py';path.write_text(script,encoding='utf-8')
    process=subprocess.run([str(backend_python()),'-X','utf8',str(path)],cwd=ROOT,
        capture_output=True,text=True,encoding='utf-8',timeout=120)
    assert process.returncode==0,process.stdout+process.stderr
    return json.loads(process.stdout)


def test_blade_only_with_flow_cad_keeps_original_span_domain(tmp_path):
    params=sample_parameters();params.geometry.vane_count=1
    params.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    params.cad_export.fillet.hub_enabled=False
    result=run_job(params,tmp_path/'job','both')['report']
    source=result['checks']['blade_solids']['main']
    assert source['root_extension_reference_mm']==0
    assert source['construction_span_domain']==[0.,1.]
    assert result['checks']['root_extension_mm']['main']>0
    artifact=result['artifacts']['mechanical']
    assert artifact['status']=='PASS'
    original=artifact['roundtrip']['main']['original']
    assert original['bbox_mm']==source['bbox_mm']
    assert original['volume_mm3']==source['volume_mm3']


def test_genuine_hub_cavity_is_never_removed(tmp_path):
    result=native_json(tmp_path,'''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_FACE,TopAbs_SHELL
from blade_designer.cad.occt_backend import shapes,OcctBackend,CadShape
outer=BRepPrimAPI_MakeBox(10,10,10).Shape()
inner=BRepPrimAPI_MakeBox(gp_Pnt(2,2,2),2,2,2).Shape()
cut=BRepAlgoAPI_Cut(outer,inner);cut.Build();shape=cut.Shape()
blade=BRepPrimAPI_MakeBox(gp_Pnt(5,5,9),1,1,3).Shape()
backend=OcctBackend()
model=backend.boolean_union(CadShape(blade,{'BLADE_PS':shapes(blade,TopAbs_FACE)}),
    CadShape(shape,{'HUB_FLOW_SURFACE':shapes(shape,TopAbs_FACE)}))
print(json.dumps({'shells':len(shapes(model.shape,TopAbs_SHELL)),
                  'volume':backend.validate_solid(model)['volume_mm3']}))
''')
    assert result['shells']==2 and abs(result['volume']-994.)<1e-6


def test_nonmanifold_root_rejected_before_fillet_builder(tmp_path):
    result=native_json(tmp_path,'''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.TopoDS import TopoDS_Compound
from OCP.TopAbs import TopAbs_FACE
from OCP.gp import gp_Pnt,gp_Vec
from blade_designer.cad.occt_backend import OcctBackend,CadShape,shapes
from blade_designer.cad.errors import FilletGenerationError
edge=BRepBuilderAPI_MakeEdge(gp_Pnt(0,0,0),gp_Pnt(1,0,0)).Edge()
faces=[shapes(BRepPrimAPI_MakePrism(edge,gp_Vec(*direction),False).Shape(),TopAbs_FACE)[0]
       for direction in [(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]]
compound=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(compound)
for face in faces:builder.Add(compound,face)
try:
 OcctBackend().root_edges(CadShape(compound,{'HUB_FLOW_SURFACE':[faces[0]],'BLADE_PS':[faces[1]]}))
except FilletGenerationError as exc:print(json.dumps(str(exc)))
else:raise AssertionError('Nonmanifold root was accepted')
''')
    assert '4 distinct adjacent faces' in result


def test_thin_annulus_sampling_respects_hole_and_does_not_mesh_original(tmp_path):
    result=native_json(tmp_path,'''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge,BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeFace
from OCP.gp import gp_Circ,gp_Ax2,gp_Pnt,gp_Dir,gp_Pln,gp_Pnt2d
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.TopAbs import TopAbs_IN,TopAbs_ON
from blade_designer.cad.cad_validation import trimmed_face_parameters
axis=gp_Ax2(gp_Pnt(0,0,0),gp_Dir(0,0,1))
outer=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(axis,1.)).Edge()).Wire()
inner=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(axis,.9999)).Edge()).Wire()
builder=BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0,0,0),gp_Dir(0,0,1)),outer,True)
builder.Add(TopoDS.Wire(inner.Reversed()));face=builder.Face()
before=BRep_Tool.Triangulation_s(face,TopLoc_Location())
points=trimmed_face_parameters(face,(.5,.25,.75,.1,.9))
assert points
assert all(BRepClass_FaceClassifier(face,gp_Pnt2d(*point),1e-7).State() in (TopAbs_IN,TopAbs_ON) for point in points)
assert before is None and BRep_Tool.Triangulation_s(face,TopLoc_Location()) is None
print(json.dumps({'count':len(points),'radii':[(x*x+y*y)**.5 for x,y in points]}))
''')
    assert result['count']>0
    assert all(.9999-1e-7<=r<=1+1e-7 for r in result['radii'])


def test_unburied_construction_cap_is_rejected(tmp_path):
    result=native_json(tmp_path,'''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from blade_designer.cad.occt_backend import OcctBackend,CadShape,shapes
from blade_designer.cad.errors import BooleanUnionError
hub=BRepPrimAPI_MakeBox(10,10,10).Shape()
blade=BRepPrimAPI_MakeBox(gp_Pnt(2,2,20),1,1,3).Shape()
try:
 OcctBackend().boolean_union(CadShape(blade,{'BLADE_HUB_CAP':[shapes(blade,TopAbs_FACE)[0]]},
    {'root_extension_span_fraction':.01,'root_extension_reference_mm':.2}),CadShape(hub))
except BooleanUnionError as exc:print(json.dumps(str(exc)))
else:raise AssertionError('An exposed construction cap was accepted')
''')
    assert 'not wholly inside' in result


def test_periodic_broadphase_separates_far_solids_but_keeps_real_overlap(tmp_path):
    result=native_json(tmp_path,'''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from blade_designer.cad.occt_backend import OcctBackend,CadShape
from blade_designer.cad.errors import InvalidSolidError
backend=OcctBackend()
report=backend.check_interference(CadShape(BRepPrimAPI_MakeBox(gp_Pnt(10,0,0),1,1,1).Shape()),2,.01)
try:backend.check_interference(CadShape(BRepPrimAPI_MakeBox(gp_Pnt(-1,-1,-1),2,2,2).Shape()),2,.01)
except InvalidSolidError as exc:report['overlap_rejected']='overlap 8' in str(exc)
else:raise AssertionError('An overlapping periodic copy was accepted')
print(json.dumps(report))
''')
    assert result['copies_checked']==1 and result['bbox_separated_copies']==1
    assert result['exact_boolean_copies']==0 and result['max_overlap_volume_mm3']==0
    assert result['overlap_rejected']


def test_root_group_separation_rejects_contact_and_missing_geometry(tmp_path):
    result=native_json(tmp_path,'''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from blade_designer.cad.occt_backend import OcctBackend,CadShape,shapes
from blade_designer.cad.errors import InvalidSolidError
first=BRepPrimAPI_MakeBox(1,1,1).Shape()
second=BRepPrimAPI_MakeBox(gp_Pnt(4,0,0),1,1,1).Shape()
a=shapes(first,TopAbs_FACE);b=shapes(second,TopAbs_FACE)
model=CadShape(first,{'HUB_FILLET_GROUP_main':a,'BLADE_GROUP_main':a,
    'HUB_FILLET_GROUP_splitter':b,'BLADE_GROUP_splitter':b},
    {'fillet_groups':{'main':{},'splitter':{}}})
backend=OcctBackend();passed=backend.check_root_group_separation(model,.01)
model.labels['HUB_FILLET_GROUP_splitter']=a
try:backend.check_root_group_separation(model,.01)
except InvalidSolidError:contact=True
else:raise AssertionError('Contact was accepted')
model.labels['HUB_FILLET_GROUP_splitter']=[]
try:backend.check_root_group_separation(model,.01)
except InvalidSolidError:missing=True
else:raise AssertionError('Missing geometry was accepted')
print(json.dumps({'passed':passed,'contact':contact,'missing':missing}))
''')
    assert len(result['passed'])==3 and result['contact'] and result['missing']
    assert all(item['surface_distance_mm']==3. for item in result['passed'])
