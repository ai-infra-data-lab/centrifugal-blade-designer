"""Boundary evidence detects local changes hidden by volume and bounding box."""
from copy import deepcopy
import json
import subprocess
import pytest
from blade_designer.cad.boundary_samples import require_boundary_samples
from blade_designer.cad.cad_validation import step_roundtrip
from blade_designer.cad.errors import CadExportError
from blade_designer.cad.client import ROOT,backend_python,prepare_job,publish_job
from blade_designer.models.cad import MechanicalExportScope
from .conftest import sample_parameters
from .test_root_interface_reconciliation import native_json
from .test_step_error_budget import MeasuredBackend


SETUP='''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Pnt
from blade_designer.cad.occt_backend import OcctBackend,CadShape
from blade_designer.cad.boundary_samples import compare_boundary_samples,require_boundary_samples
from blade_designer.cad.errors import CadExportError
backend=OcctBackend()
def cavity(x):
 cut=BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(10,10,10).Shape(),BRepPrimAPI_MakeBox(gp_Pnt(x,2,2),1,1,1).Shape());cut.Build()
 return CadShape(cut.Shape())
'''


def test_same_boundary_and_rigid_location_preserve_geometry_and_cover_cavity_faces(tmp_path):
    result=native_json(tmp_path,SETUP+'''
from OCP.gp import gp_Trsf,gp_Ax1,gp_Dir,gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
transform=gp_Trsf();transform.SetRotation(gp_Ax1(gp_Pnt(),gp_Dir(0,0,1)),.37)
transform.SetTranslationPart(gp_Vec(17,2,-5))
a=CadShape(BRepBuilderAPI_Transform(cavity(2).shape,transform,False).Shape())
b=CadShape(BRepBuilderAPI_Transform(cavity(2).shape,transform,False).Shape())
before=[backend._solid_fingerprint(model.shape) for model in (a,b)]
report=compare_boundary_samples(a,b,.01);require_boundary_samples(report)
assert before==[backend._solid_fingerprint(model.shape) for model in (a,b)]
print(json.dumps(report))
''')
    assert result['status']=='PASS_SAMPLED'
    assert result['global_surface_error']==result['global_normal_alignment']=='NOT_TESTED'
    for name in ('source_to_imported','imported_to_source'):
        row=result[name]
        assert row['face_count']==12 and row['sample_count']==108
        assert row['max_distance_mm']<1e-9 and row['max_normal_angle_deg']<1e-4


def test_bidirectional_internal_surface_change_and_reversed_normal_rejected(tmp_path):
    result=native_json(tmp_path,SETUP+'''
from OCP.TopoDS import TopoDS
from OCP.TopAbs import TopAbs_FACE
from blade_designer.cad.occt_backend import shapes
a,b=cavity(2),cavity(6)
first,second=backend.validate_solid(a),backend.validate_solid(b)
assert abs(first['volume_mm3']-second['volume_mm3'])<1e-9 and first['bbox_mm']==second['bbox_mm']
shifted=compare_boundary_samples(a,b,.01)
face=TopoDS.Face(shapes(a.shape,TopAbs_FACE)[0])
flipped=compare_boundary_samples(CadShape(face),CadShape(face.Reversed()),.01)
for report in (shifted,flipped):
 try:require_boundary_samples(report)
 except CadExportError:pass
 else:raise AssertionError('Changed boundary accepted')
print(json.dumps({'shifted':shifted,'flipped':flipped}))
''')
    for direction in ('source_to_imported','imported_to_source'):
        assert result['shifted'][direction]['max_distance_mm']==pytest.approx(2.75)
        assert result['flipped'][direction]['max_distance_mm']==0
        assert result['flipped'][direction]['max_normal_angle_deg']==180


def test_worker_checks_boundary_faces_of_mechanical_and_fluid_step(native_assembly):
    report=native_assembly['report'];assert not report.get('error'),report.get('error')
    tolerance=native_assembly['params'].cad_export.surface_tolerance_mm
    for name in ('mechanical','turbogrid_cad'):
        audit=report['artifacts'][name]['roundtrip']['boundary_surface_samples']
        assert audit['status']=='PASS_SAMPLED'
        assert audit['global_surface_error']==audit['global_normal_alignment']=='NOT_TESTED'
        for direction in ('source_to_imported','imported_to_source'):
            data=audit[direction]
            assert data['face_count']>=4 and len(data['faces'])==data['face_count']
            assert data['sample_count']>=data['face_count']
            assert all(row['sample_count']>0 and row['max_distance_mm']<=tolerance and
                row['max_normal_angle_deg']<90 for row in data['faces'])


@pytest.mark.parametrize('direction',['source','imported'])
@pytest.mark.parametrize('field,value',[
    ('bbox_mm',[float('nan'),0,0,1,1,1]),('volume_mm3',float('nan')),
    ('surface_area_mm2',float('nan')),('max_edge_tolerance_mm',float('nan')),
    ('solid_count',True),('bbox_mm',[0,0,0,1,1]),('volume_mm3',0.),
])
def test_step_metrics_must_be_complete_positive_and_finite(tmp_path,direction,field,value):
    class BrokenMetrics(MeasuredBackend):
        def validate_solid(self,model):
            result=super().validate_solid(model)
            if (model=='imported')==(direction=='imported'):result[field]=value
            return result
    path=tmp_path/'metrics.step';path.write_text('SI_UNIT(.MILLI.,.METRE.)')
    with pytest.raises(CadExportError):step_roundtrip(BrokenMetrics(shift=0),'source',path,.01)


@pytest.mark.parametrize('tolerance',[0.,-1.,float('nan'),float('inf'),True])
def test_nonfinite_or_invalid_tolerance_rejected(tmp_path,tolerance):
    path=tmp_path/'metrics.step';path.write_text('SI_UNIT(.MILLI.,.METRE.)')
    with pytest.raises(CadExportError):step_roundtrip(MeasuredBackend(),'source',path,tolerance)


def test_overflowed_comparison_budget_is_not_an_unlimited_allowance(tmp_path):
    class OverflowMetrics(MeasuredBackend):
        def validate_solid(self,model):
            result=super().validate_solid(model);result['surface_area_mm2']=1e308;return result
    path=tmp_path/'metrics.step';path.write_text('SI_UNIT(.MILLI.,.METRE.)')
    with pytest.raises(CadExportError):step_roundtrip(OverflowMetrics(),'source',path,1e308)


@pytest.mark.parametrize('mutation',['missing_direction','missing_face','duplicate_index','missing_samples','nan','normal_reversal','false_global_claim'])
def test_incomplete_or_falsely_promoted_evidence_rejected(mutation):
    face={'face_index':0,'sample_count':1,'max_distance_mm':0.,'max_normal_angle_deg':0.,'nearest_target_faces':[0]}
    section={'face_count':1,'sample_count':1,'max_distance_mm':0.,'max_normal_angle_deg':0.,'faces':[face]}
    report={'schema_version':1,'unit':'mm','status':'PASS_SAMPLED','requested_tolerance_mm':.01,
        'global_surface_error':'NOT_TESTED','global_normal_alignment':'NOT_TESTED',
        'source_to_imported':deepcopy(section),'imported_to_source':deepcopy(section)}
    require_boundary_samples(report)
    if mutation=='missing_direction':del report['imported_to_source']
    elif mutation=='missing_face':report['source_to_imported']['faces']=[]
    elif mutation=='duplicate_index':report['source_to_imported']['faces'][0]['face_index']=1
    elif mutation=='missing_samples':report['source_to_imported']['faces'][0]['sample_count']=0
    elif mutation=='nan':report['source_to_imported']['faces'][0]['max_distance_mm']=float('nan')
    elif mutation=='normal_reversal':report['source_to_imported']['faces'][0]['max_normal_angle_deg']=180.
    else:report['global_surface_error']='PASS'
    with pytest.raises(CadExportError):require_boundary_samples(report)


def test_native_step_fault_preserves_previous_output_even_with_equal_volume_and_bbox(tmp_path):
    p=sample_parameters();p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    job=prepare_job(p,'mechanical',tmp_path/'job')
    script=tmp_path/'fault.py'
    script.write_text(SETUP+'''
from blade_designer.cad.worker import execute
from blade_designer.cad.cad_validation import step_roundtrip
job=Path(sys.argv[1]);source=cavity(2);changed=cavity(6)
# Fault injection only: real native solids/STEP, independent of blade generator.
OcctBackend.create_blade_solid=lambda self,*args,**kwargs:source
native_export=OcctBackend.export_step
def wrong_export(self,model,path):
 return native_export(self,changed if path.name.startswith('blade_only_') else model,path)
OcctBackend.export_step=wrong_export
report=execute(job)
old,_=step_roundtrip(backend,source,job/'outputs/mechanical/blade_only_main_NO_FILLET.step',.01)
assert old['status']=='PASS' and report['overall']=='FAIL'
assert report['error']['type']=='CadExportError' and not report['artifacts'].get('mechanical')
''',encoding='utf-8')
    process=subprocess.run([str(backend_python()),'-X','utf8',str(script),str(job)],cwd=ROOT,
        capture_output=True,text=True,encoding='utf-8',timeout=120)
    assert process.returncode==0,process.stdout+process.stderr
    case=tmp_path/'case';folder=case/'mechanical';folder.mkdir(parents=True)
    old=folder/'blade_only_main_NO_FILLET.step';old.write_bytes(b'previous verified STEP sentinel')
    result=publish_job(job,case,p)
    assert result['overall']=='FAIL' and old.read_bytes()==b'previous verified STEP sentinel'
    assert not (case/'validation/cad_validation.json').exists()
    assert json.loads((job/'result.json').read_text(encoding='utf-8'))['error']['type']=='CadExportError'
