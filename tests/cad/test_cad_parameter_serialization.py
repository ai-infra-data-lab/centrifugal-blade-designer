from dataclasses import asdict
from copy import deepcopy
import json
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.cad import MechanicalExportScope,validate_cad_parameters
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.cad.client import backend_python
from blade_designer.cad.errors import BackendUnavailableError
from .conftest import sample_parameters

def test_old_json_omits_default_cad_but_loads_safe_defaults(tmp_path):
    p=BladeParameters();path=tmp_path/'old.json';save_project(path,p);raw=json.loads(path.read_text())
    assert raw['schema_version']=='0.3' and 'cad_export' not in raw
    q=load_project(path);assert q==p and q.cad_export.fillet.hub_enabled and q.cad_export.fillet.hub_radius_mm==8
    assert q.cad_export.disk.backside is None and q.cad_export.disk.bore_radius_mm is None

def test_v04_disk_and_fillet_roundtrip(tmp_path):
    p=sample_parameters();p.cad_export.mechanical_scope=MechanicalExportScope.FULL_IMPELLER
    path=tmp_path/'new.json';save_project(path,p);assert json.loads(path.read_text())['schema_version']=='0.4'
    assert load_project(path)==p

@pytest.mark.parametrize('value',[float('nan'),0,-1,True])
def test_invalid_cad_parameters_protect_project(tmp_path,value):
    p=BladeParameters();path=tmp_path/'p.json';save_project(path,p);before=path.read_bytes();p.cad_export.fillet.hub_radius_mm=value
    with pytest.raises(ValueError):save_project(path,p)
    assert path.read_bytes()==before

def test_missing_backend_does_not_block_coordinate_engine(monkeypatch,tmp_path):
    from blade_designer.cad import client
    from blade_designer.geometry.geometry_3d import generate_impeller
    monkeypatch.setattr(client,'ROOT',tmp_path)
    with pytest.raises(BackendUnavailableError):backend_python()
    assert generate_impeller(BladeParameters()).sections
