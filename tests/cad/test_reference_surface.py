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


def test_worker_adopted_role_densities_reproduce_native_base_patches(native_blade):
    from blade_designer.cad.reference_report import adopted_surface_counts
    from blade_designer.fileio.geometry_source import geometry_source
    params=native_blade['params'];report=native_blade['report']
    counts=adopted_surface_counts(report,geometry_source(params,'meridional_3d').snapshot_hash,'main')
    assert counts==report['checks']['blade_solids']['main']['surface_grid_counts']
    script='''
import json,sys
from pathlib import Path
import numpy as np
from blade_designer.fileio.project_io import load_project
from blade_designer.fileio.geometry_source import geometry_source
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.cad_surface_reference import reference_surfaces
from blade_designer.cad.reference_report import adopted_surface_counts
from blade_designer.cad.occt_backend import OcctBackend
job=Path(sys.argv[1]);p=load_project(job/'geometry_snapshot.json')
report=json.loads((job/'result.json').read_text(encoding='utf-8'))
counts=adopted_surface_counts(report,geometry_source(p,'meridional_3d').snapshot_hash,'main')
g=generate_impeller(p);reference=reference_surfaces(g.sections,p.sections,counts)
request=json.loads((job/'request.json').read_text(encoding='utf-8'));group=next(s for s in request['groups'] if s['name']=='main')
payload=[]
with np.load(job/'geometry.npz',allow_pickle=False) as arrays:
 for i,span in enumerate(group['spans']):
  d={'span':span,**{k+'_type':v for k,v in group['edge_types'][i].items()}}
  for role in ('le','ps','te','ss'):
   prefix=f'main_{i}_{role}';d[role]=arrays[prefix];d[role+'_xi']=arrays[prefix+'_xi']
  payload.append(d)
backend=OcctBackend();tangents=backend._join_tangents(payload)
spans=np.linspace(0,1,13);xi=np.linspace(0,1,23)
for role in counts:
 cad=backend.create_surface([s[role] for s in payload],counts[role],[s[role+'_xi'] for s in payload],group['spans'],tangents[role])
 actual=np.array([[[q.X(),q.Y(),q.Z()] for q in [cad.Value(float(s),float(t)) for t in xi]] for s in spans])
 np.testing.assert_allclose(reference[role].evaluate_grid(spans,xi),actual,atol=5e-12,rtol=0)
'''
    result=subprocess.run([str(backend_python()),'-X','utf8','-c',script,str(native_blade['job'])],cwd=ROOT,
        capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
