import json
from blade_designer.fileio.project_io import load_project, save_project


def test_v01_migration(tmp_path):
    old = {"schema_version":"0.1","geometry":{"r_le":100.,"r_te":160.,"theta_le_deg":12.,"vane_count":20,"n_points":301},
           "angle":{"xi":[0.,.4,1.],"alpha_deg":[65.,55.,40.]},
           "thickness":{"t_le":1.,"t_max":4.,"xi_tmax":.35,"t_te":.5}}
    path = tmp_path/"old.json"
    original = json.dumps(old)
    path.write_text(original)
    p = load_project(path)
    assert [x.m_norm for x in p.blade_angle.points] == old["angle"]["xi"]
    assert [x.value for x in p.blade_angle.points] == old["angle"]["alpha_deg"]
    assert [(x.m_norm,x.value) for x in p.thickness.points] == [(0,1),(.35,4),(1,.5)]
    assert list(vars(p.output_points).values()) == [21,101,21,101]
    assert p.export.significant_digits == 6
    assert path.read_text() == original
    save_project(tmp_path/"new.json",p)
    assert load_project(tmp_path/"new.json") == p
