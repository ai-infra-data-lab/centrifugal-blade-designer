import json
import subprocess
import pytest
from blade_designer.cad.client import backend_python,ROOT
from blade_designer.models.cad import MechanicalExportScope
from blade_designer.models.parameters import EdgeType
from blade_designer.fileio.project_io import load_project
from .conftest import sample_parameters,run_job


def test_saved_default_blade_only_step_uses_converged_volume(tmp_path):
    p=load_project(ROOT/'blade_designer/defaults/default_project.json')
    row=next(row for row in p.blade_rows if row.kind=='impeller')
    p.active_blade_row=row.identifier
    row.parameters.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    result=run_job(p,tmp_path/'default','mechanical');r=result['report']
    assert r['artifacts'].get('mechanical',{}).get('status')=='PASS',r.get('error')
    step=r['artifacts']['mechanical']['roundtrip']['main']
    assert step['volume_difference_mm3']<=step['volume_tolerance_mm3']
    assert 'Gauss-Kronrod' in step['original']['volume_integration']
    assert max(step[key]['max_edge_tolerance_mm'] for key in ('original','imported'))<=.01


def test_beta_thickness_edge_and_rake_regenerate_native_cad(native_blade,tmp_path):
    p=sample_parameters();p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    p.impeller_te_rake_deg=5.
    for section in p.sections:
        section.blade_angle.points[-1].value=30.
        section.thickness.points[1].value=26.
        section.edge_parameters.le_type=EdgeType.ELLIPTICAL
        section.edge_parameters.le_ellipse_ratio=1.2
    result=run_job(p,tmp_path/'changed','mechanical');report=result['report']
    assert report['blade_solid_status']=='PASS',report.get('error')
    before=native_blade['report']
    assert report['parameter_snapshot_hash']!=before['parameter_snapshot_hash']
    assert abs(report['checks']['result']['volume_mm3']-before['checks']['result']['volume_mm3'])>1.
    assert report['artifacts']['mechanical']['sha256']!=before['artifacts']['mechanical']['sha256']


def test_native_primitive_small_and_r8_fillet_and_collision_guard(tmp_path):
    try:python=backend_python()
    except Exception as exc:pytest.skip(str(exc))
    # Independent analytic box: no application blade coordinates or regression fixtures.
    code='''
import sys,json
from pathlib import Path
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopAbs import TopAbs_EDGE
from blade_designer.cad.occt_backend import OcctBackend,CadShape,shapes
from blade_designer.cad.cad_validation import step_roundtrip
from blade_designer.cad.errors import InvalidSolidError
b=OcctBackend();box=CadShape(BRepPrimAPI_MakeBox(40.,50.,60.).Shape())
assert abs(b.validate_solid(box)['volume_mm3']-120000.)<1e-6
out={}
for radius in (1.,8.):
    rounded=b.apply_fillet(box,shapes(box.shape,TopAbs_EDGE),radius)
    assert rounded.metrics['fillet_radius_mm']==radius
    assert b.validate_solid(rounded)['volume_mm3']<120000.
    path=Path(sys.argv[1])/('primitive_R'+str(radius)+'.step')
    b.export_step(rounded,path);out[str(radius)]=step_roundtrip(b,rounded,path,.01)[0]
try:b.check_pair_interference(box,box,.01)
except InvalidSolidError:out['collision_rejected']=True
else:raise AssertionError('Overlapping blade features accepted')
(Path(sys.argv[1])/'primitive.json').write_text(json.dumps(out),encoding='utf-8')
'''
    run=subprocess.run([str(python),'-X','utf8','-c',code,str(tmp_path)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=180)
    assert run.returncode==0,run.stdout+run.stderr
    checks=json.loads((tmp_path/'primitive.json').read_text(encoding='utf-8'))
    assert checks['collision_rejected'] and checks['8.0']['status']=='PASS'
