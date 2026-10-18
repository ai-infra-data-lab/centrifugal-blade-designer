"""Compare Bernstein area-vector envelopes with actual native D1 derivatives."""
import subprocess
import pytest
from blade_designer.cad.client import backend_python, ROOT
from blade_designer.cad.errors import BackendUnavailableError


def test_native_area_vectors_are_inside_main_splitter_cell_envelopes():
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
from blade_designer.geometry.surface_regularity import surface_jacobian_envelope
from blade_designer.cad.occt_backend import OcctBackend
p=BladeParameters();p.impeller_te_rake_deg=12.
p.tip_clearance=TipClearanceParameters(.4,.8)
p.splitter=SplitterParameters(sections=deepcopy(p.sections))
g=generate_impeller(p);backend=OcctBackend()
for sections in (g.sections,g.splitter_sections):
 reference=reference_surfaces(sections,p.sections,33);payload=[]
 for section,profile in zip(sections,p.sections):
  d={'span':section.span,'le_type':profile.edge_parameters.le_type.value,'te_type':profile.edge_parameters.te_type.value}
  for role in reference:
   c=getattr(section,'master_'+role);d[role]=c.xyz;d[role+'_xi']=cad_curve_coordinates(c)
  payload.append(d)
 tangents=backend._join_tangents(payload)
 for role,surface in reference.items():
  envelope=surface_jacobian_envelope(surface,singular_mm2=1e-12)
  cad=backend.create_surface([s[role] for s in payload],33,[s[role+'_xi'] for s in payload],[s['span'] for s in payload],tangents[role])
  for cell in envelope['cells']:
   u=np.linspace(*cell['span_range'],3);v=np.linspace(*cell['xi_range'],3)
   for s in u:
    for t in v:
     point=gp_Pnt();ds=gp_Vec();dx=gp_Vec();cad.D1(float(s),float(t),point,ds,dx)
     observed=ds.Crossed(dx).Magnitude()
     # Numerical derivative/area comparison only; no CAD tolerance changes.
     allowance=4096*np.finfo(float).eps*max(1.,cell['upper_mm2'])
     assert cell['lower_mm2']-allowance <= observed <= cell['upper_mm2']+allowance,(role,cell,observed)
  assert envelope['roundoff_certified'] is False
'''
    result=subprocess.run([str(python),'-X','utf8','-c',script],cwd=ROOT,
                          capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
