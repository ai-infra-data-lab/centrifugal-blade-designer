"""Independent OCCT D1 comparison of oriented base-patch normals."""
import subprocess
import pytest
from blade_designer.cad.client import backend_python, ROOT
from blade_designer.cad.errors import BackendUnavailableError


def test_native_main_splitter_normals_are_inside_corresponding_cell_bounds():
    try:
        python=backend_python()
    except BackendUnavailableError as exc:
        pytest.skip('Optional CAD backend unavailable: '+str(exc))
    script='''
from copy import deepcopy
import numpy as np
from OCP.gp import gp_Pnt,gp_Vec
from blade_designer.models.parameters import BladeParameters,SplitterParameters,TipClearanceParameters
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.cad_surface_reference import reference_surfaces
from blade_designer.geometry.surface_correspondence import cad_curve_coordinates
from blade_designer.geometry.surface_orientation import surface_normal_envelope
from blade_designer.cad.occt_backend import OcctBackend
p=BladeParameters();p.impeller_te_rake_deg=12.
p.tip_clearance=TipClearanceParameters(.4,.8)
p.splitter=SplitterParameters(sections=deepcopy(p.sections))
g=generate_impeller(p);backend=OcctBackend()
for sections in (g.sections,g.splitter_sections):
 first=reference_surfaces(sections,p.sections,33)
 second=reference_surfaces(sections,p.sections,65)
 payload=[]
 for section,profile in zip(sections,p.sections):
  d={'span':section.span,'le_type':profile.edge_parameters.le_type.value,'te_type':profile.edge_parameters.te_type.value}
  for role in first:
   c=getattr(section,'master_'+role);d[role]=c.xyz;d[role+'_xi']=cad_curve_coordinates(c)
  payload.append(d)
 tangents=backend._join_tangents(payload)
 for role in first:
  envelope=surface_normal_envelope(first[role],second[role],singular_mm2=1e-12)
  assert envelope['unresolved_cells']<envelope['cell_count'],role
  native=[backend.create_surface([s[role] for s in payload],n,[s[role+'_xi'] for s in payload],
          [s['span'] for s in payload],tangents[role]) for n in (33,65)]
  for cell in envelope['cells']:
   observed=[]
   for s in np.linspace(*cell['span_range'],3):
    for t in np.linspace(*cell['xi_range'],3):
     normals=[]
     for cad in native:
      point=gp_Pnt();ds=gp_Vec();dx=gp_Vec();cad.D1(float(s),float(t),point,ds,dx)
      v=ds.Crossed(dx);assert v.Magnitude()>1e-12
      normals.append(np.array([v.X(),v.Y(),v.Z()])/v.Magnitude())
     angle=np.degrees(np.arctan2(np.linalg.norm(np.cross(*normals)),np.dot(*normals)))
     observed.append(angle)
     # Arithmetic comparison in degrees, not a CAD/design tolerance.
     allowance=4096*np.finfo(float).eps*180
     if cell['angle_upper_degrees'] is not None:
      assert angle <= cell['angle_upper_degrees']+allowance,(role,cell,angle)
   assert abs(max(observed)-cell['sample_max_degrees']) <= allowance,(role,cell,observed)
   if cell['angle_upper_degrees'] is None:
    assert min(cell['first_lower_mm2'],cell['second_lower_mm2'])<=1e-12 or cell['sample_undefined_pairs']>0
  if envelope['unresolved_cells']:
   assert envelope['angle_upper_degrees'] is None
  assert envelope['roundoff_certified'] is False
'''
    result=subprocess.run([str(python),'-X','utf8','-c',script],cwd=ROOT,
                          capture_output=True,text=True,encoding='utf-8',timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
