"""Factory reference against the actual OCCT surface at interior points."""
import subprocess
import pytest
from blade_designer.cad.client import backend_python,ROOT
from blade_designer.cad.errors import BackendUnavailableError


@pytest.mark.parametrize('density',[33,129])
def test_reference_factory_matches_native_surface(density):
    try:python=backend_python()
    except BackendUnavailableError as exc:pytest.skip('Optional CAD backend unavailable: '+str(exc))
    script='''
import numpy as np
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.cad_surface_reference import reference_surfaces
from blade_designer.geometry.surface_correspondence import cad_curve_coordinates
from blade_designer.cad.occt_backend import OcctBackend
p=BladeParameters();g=generate_impeller(p);backend=OcctBackend()
reference=reference_surfaces(g.sections,p.sections,DENSITY)
payload=[]
for s,profile in zip(g.sections,p.sections):
 d={'span':s.span,'le_type':profile.edge_parameters.le_type.value,'te_type':profile.edge_parameters.te_type.value}
 for role in ('le','ps','te','ss'):
  c=getattr(s,'master_'+role);d[role]=c.xyz;d[role+'_xi']=cad_curve_coordinates(c)
 payload.append(d)
tangents=backend._join_tangents(payload)
spans=np.linspace(0,1,13);xi=np.linspace(0,1,23)
for role in reference:
 cad=backend.create_surface([s[role] for s in payload],DENSITY,[s[role+'_xi'] for s in payload],[s['span'] for s in payload],tangents[role])
 observed=np.array([[[q.X(),q.Y(),q.Z()] for q in [cad.Value(float(s),float(t)) for t in xi]] for s in spans])
 np.testing.assert_allclose(reference[role].evaluate_grid(spans,xi),observed,atol=5e-12,rtol=0)
'''.replace('DENSITY',str(density))
    result=subprocess.run([str(python),'-X','utf8','-c',script],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
