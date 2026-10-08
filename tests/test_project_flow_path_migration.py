import json
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from blade_designer.fileio.project_migration import migrate_v03_flow_path
from blade_designer.fileio.project_io import load_project,save_project
from blade_designer.geometry.geometry_3d import generate_impeller

FIXTURES=Path(__file__).parent/"fixtures"

def test_earlier_v03_keeps_original_wall_geometry_and_coordinates(tmp_path):
    path=FIXTURES/"old_v03_flow_path.json"
    original=path.read_bytes();data=json.loads(original)
    before=deepcopy(data);upgraded=migrate_v03_flow_path(data)
    assert data==before
    assert upgraded["hub"]==data["hub"] and upgraded["shroud"]==data["shroud"]
    assert not upgraded["flow_path"]["align_blade_stations_to_crossflow"]
    p=load_project(path);g=generate_impeller(p)
    assert path.read_bytes()==original
    with np.load(FIXTURES/"old_v03_profiles.npz") as reference:
        for i,section in enumerate(g.sections):
            for name in ("camber","master_ps","master_ss","master_le","master_te"):
                np.testing.assert_allclose(getattr(section,name).xyz,reference[f"{i}_{name}"],rtol=0,atol=3e-6)
    save_project(tmp_path/"upgraded.json",p)
    assert load_project(tmp_path/"upgraded.json")==p
    saved=json.loads((tmp_path/"upgraded.json").read_text())
    assert "m_blade_norm" in saved["blade_angle"]["points"][0]
    assert "m_norm" not in saved["blade_angle"]["points"][0]

def test_new_flow_path_precision_and_legacy_coordinate_alias(tmp_path):
    from blade_designer.models.parameters import BladeParameters,DistributionPoint
    from blade_designer.models.flow_path import StationType
    p=BladeParameters()
    p.flow_path.set_position(StationType.DIF_LE,.9123456789012345)
    p.sections[1].blade_angle.points[1]=DistributionPoint(m_norm=.2512345678901234,value=46)
    save_project(tmp_path/"new.json",p)
    assert load_project(tmp_path/"new.json")==p
    p.flow_path.stations[3].m_flow_norm=.8
    with pytest.raises(ValueError):save_project(tmp_path/"invalid.json",p)
    assert not (tmp_path/"invalid.json").exists()

def test_malformed_station_data_does_not_load(tmp_path):
    from blade_designer.models.parameters import BladeParameters
    p=tmp_path/"bad.json";save_project(p,BladeParameters())
    data=json.loads(p.read_text());data["flow_path"]["stations"][2]["other"]=1
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="station fields"):load_project(p)

def test_existing_normal_cut_v03_keeps_every_master_coordinate(tmp_path):
    path=FIXTURES/"flow_path_before_additional.json"
    original=path.read_bytes();p=load_project(path);g=generate_impeller(p)
    with np.load(FIXTURES/"flow_path_before_additional.npz") as reference:
        for i,section in enumerate(g.sections):
            for name in ("camber","master_ps","master_ss","master_le","master_te"):
                np.testing.assert_allclose(getattr(section,name).xyz,reference[f"{i}_{name}"],rtol=0,atol=1e-12)
    assert path.read_bytes()==original
    save_project(tmp_path/"upgraded.json",p)
    assert load_project(tmp_path/"upgraded.json")==p
