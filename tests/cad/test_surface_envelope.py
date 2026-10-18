"""The numerical envelope also encloses sampled native base-patch differences."""
import subprocess
import pytest
from blade_designer.cad.client import backend_python, ROOT
from blade_designer.cad.errors import BackendUnavailableError


def test_native_patch_differences_stay_inside_common_control_envelope():
    try:
        python=backend_python()
    except BackendUnavailableError as exc:
        pytest.skip('Optional CAD backend unavailable: '+str(exc))
    script='''
import numpy as np
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.cad_surface_reference import reference_surfaces
from blade_designer.geometry.surface_correspondence import cad_curve_coordinates
from blade_designer.geometry.surface_envelope import surface_distance_envelope
from blade_designer.cad.occt_backend import OcctBackend
p=BladeParameters();g=generate_impeller(p);backend=OcctBackend()
first=reference_surfaces(g.sections,p.sections,33)
second=reference_surfaces(g.sections,p.sections,129)
payload=[]
for section,profile in zip(g.sections,p.sections):
 d={'span':section.span,'le_type':profile.edge_parameters.le_type.value,'te_type':profile.edge_parameters.te_type.value}
 for role in first:
  curve=getattr(section,'master_'+role);d[role]=curve.xyz;d[role+'_xi']=cad_curve_coordinates(curve)
 payload.append(d)
tangents=backend._join_tangents(payload)
spans=np.linspace(0,1,13);xi=np.linspace(0,1,23)
for role in first:
 envelope=surface_distance_envelope(first[role],second[role],refinements=1)
 native=[]
 for count in (33,129):
  cad=backend.create_surface([s[role] for s in payload],count,[s[role+'_xi'] for s in payload],[s['span'] for s in payload],tangents[role])
  native.append(np.array([[[q.X(),q.Y(),q.Z()] for q in [cad.Value(float(s),float(t)) for t in xi]] for s in spans]))
 observed=np.max(np.linalg.norm(native[0]-native[1],axis=-1))
 # Existing native/numeric comparison scale; not a relaxed CAD tolerance.
 assert observed <= envelope['control_upper_mm']+5e-12,(role,observed,envelope)
 assert envelope['roundoff_certified'] is False
'''
    result=subprocess.run([str(python),'-X','utf8','-c',script],cwd=ROOT,
                          capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
