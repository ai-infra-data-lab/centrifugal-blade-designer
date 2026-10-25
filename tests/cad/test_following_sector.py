"""Real kernel tests run through the isolated CAD environment, not fake BREP."""
import subprocess
from blade_designer.cad.client import backend_python,ROOT


def test_native_following_tool_and_whole_blade_retention(tmp_path):
    script=r'''
import numpy as np
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_Transform
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.TopAbs import TopAbs_FACE
from blade_designer.cad.occt_backend import OcctBackend,CadShape,shapes
from blade_designer.cad.following_sector import cut_following_sector
from blade_designer.cad.cad_validation import step_roundtrip
from OCP.gp import gp_Pnt,gp_Trsf,gp_Vec
backend=OcctBackend()
# A genuinely swept blade winds more than one pitch from LE to TE. No fixed
# pair of radial planes can retain it. The curved cut must keep its faces intact.
hub=BRepPrimAPI_MakeCylinder(100.,5.).Shape()
loft=BRepOffsetAPI_ThruSections(True,False,1e-7)
for radius in np.linspace(40.,75.,9):
    theta=.03*(radius-40.)
    c=np.array([radius*np.cos(theta),radius*np.sin(theta)])
    tangent=np.array([-np.sin(theta),np.cos(theta)])
    wire=BRepBuilderAPI_MakePolygon()
    for offset,z in ((-2.,4.),(2.,4.),(2.,19.),(-2.,19.)):
        xy=c+offset*tangent;wire.Add(gp_Pnt(*map(float,(*xy,z))))
    wire.Close();loft.AddWire(wire.Wire())
loft.Build();assert loft.IsDone();blade=loft.Shape()
def wheel(displace=False):
    full=BRepPrimAPI_MakeCylinder(100.,5.).Shape();labels={}
    for i in range(8):
        copy=backend.rotate(CadShape(blade),2*np.pi*i/8).shape
        if displace and i==4:
            move=gp_Trsf();move.SetTranslation(gp_Vec(-2.,0.,0.))
            copy=BRepBuilderAPI_Transform(copy,move,True).Shape()
        union=BRepAlgoAPI_Fuse(full,copy);union.Build();assert union.IsDone()
        labels=backend._history_labels(union,labels)
        faces=backend._history_labels(union,{'blade':shapes(copy,TopAbs_FACE)})['blade']
        labels['BLADE_GROUP_main@'+str(i)]=faces
        full=union.Shape()
    return CadShape(full,labels)
sections=[]
for z in (5.,19.):
    r=np.linspace(40.,75.,21)
    theta=.03*(r-40.)
    ps=np.column_stack((r*np.cos(theta)+2*np.sin(theta),r*np.sin(theta)-2*np.cos(theta),np.full_like(r,z)))
    ss=np.column_stack((r*np.cos(theta)-2*np.sin(theta),r*np.sin(theta)+2*np.cos(theta),np.full_like(r,z)))
    sections.append({'ps':ps,'ss':ss,'le':np.stack((ps[0],ss[0])),'te':np.stack((ps[-1],ss[-1]))})
source=wheel()
backend.validate_solid(source)  # production passes an already validated wheel
fingerprint=backend._solid_fingerprint(source.shape)
result=cut_following_sector(backend,source,[('main',sections)],8,.01)
assert backend._solid_fingerprint(source.shape)==fingerprint
assert result.metrics['following_sector']['blade_and_fillet_faces_unchanged']
assert result.metrics['following_sector']['retained_groups']==['main@0']
assert backend.validate_solid(result)['solid_count']==1
from pathlib import Path
target=Path(__import__('sys').argv[1])/'sector.step'
backend.export_step(result,target)
checked,_=step_roundtrip(backend,result,target,.01)
assert checked['status']=='PASS'
assert result.metrics['following_sector']['reconstruction']['status']=='PASS_SAMPLED_VOLUME_BUDGET'
assert result.metrics['following_sector']['reconstruction']['global_material_coverage']=='NOT_CONFIRMED'
# Move the proposed cut onto a blade. Exact kernel distance must reject this
# rather than modifying the blade or overwriting the already valid STEP.
from unittest.mock import patch
from blade_designer.geometry.sector_boundary import blade_following_phase
from blade_designer.cad.errors import InvalidSolidError
phase=blade_following_phase([('main',sections)],8)
phase.offset=0.
before=target.read_bytes()
with patch('blade_designer.geometry.sector_boundary.blade_following_phase',return_value=phase):
    try:cut_following_sector(backend,source,[('main',sections)],8,.01)
    except InvalidSolidError as exc:assert 'intersects' in str(exc)
    else:raise AssertionError('A blade-crossing cut was accepted')
assert target.read_bytes()==before
# The same volume can hide a nonperiodic blade: a radial translation within
# the cylindrical hub preserves its overlap volume, but changes its boundary.
# Rebuilding the selected passage must reject that mismatch, without weakening
# the native validity/volume gates or touching an existing successful output.
from blade_designer.cad.errors import CadExportError
bad=wheel(True)
bad_metrics=backend.validate_solid(bad)
assert abs(bad_metrics['volume_mm3']-backend.validate_solid(source)['volume_mm3'])<1e-5
bad_fingerprint=backend._solid_fingerprint(bad.shape)
try:cut_following_sector(backend,bad,[('main',sections)],8,.01)
except CadExportError as exc:assert 'boundary distance or normal samples' in str(exc)
else:raise AssertionError('Nonperiodic equal-volume blade geometry was accepted')
assert backend._solid_fingerprint(bad.shape)==bad_fingerprint
assert target.read_bytes()==before
print('FOLLOWING_NATIVE_PASS')
'''
    result=subprocess.run([str(backend_python()),'-X','utf8','-c',script,str(tmp_path)],cwd=ROOT,
                          capture_output=True,text=True,encoding='utf-8',timeout=360)
    (tmp_path/'native.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr
    assert 'FOLLOWING_NATIVE_PASS' in result.stdout
