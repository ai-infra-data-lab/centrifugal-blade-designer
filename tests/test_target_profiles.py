from copy import deepcopy
import json
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.fileio.project_io import save_project,load_project

def test_independent_profiles_generate_independently():
    p=BladeParameters();engine=BladeDesigner()
    before=deepcopy(p);original_diff=engine.generate_diffuser(p);original_imp=engine.generate_3d(p)
    p.sections[0].blade_angle.points[1].value=40
    p.sections[0].thickness.points[1].value=5
    current_diff=engine.generate_diffuser(p);current_imp=engine.generate_3d(p)
    np.testing.assert_array_equal(original_diff.camber.y,current_diff.camber.y)
    assert not np.allclose(original_imp.sections[0].camber.xyz,current_imp.sections[0].camber.xyz)
    assert p.diffuser_profile==before.diffuser_profile
    p.diffuser_profile.blade_angle.points[1].value=32
    p.diffuser_profile.thickness.points[1].value=6
    modified_imp=engine.generate_3d(p);modified_diff=engine.generate_diffuser(p)
    for a,b in zip(current_imp.sections,modified_imp.sections):np.testing.assert_array_equal(a.master_ps.xyz,b.master_ps.xyz)
    assert not np.allclose(current_diff.master_surfaces.ps.xy,modified_diff.master_surfaces.ps.xy)

def test_new_profile_roundtrip_and_old_project_migration(tmp_path):
    p=BladeParameters();p.diffuser_profile.blade_angle.points[1].value=31.123456789012345
    p.diffuser_profile.thickness.points[1].value=6.123456789012345
    path=tmp_path/"separate.json";save_project(path,p);assert load_project(path)==p
    data=json.loads(path.read_text());data.pop("diffuser_profile")
    path.write_text(json.dumps(data))
    legacy=load_project(path)
    assert legacy.diffuser_profile.blade_angle==legacy.sections[0].blade_angle
    assert legacy.diffuser_profile.blade_angle is not legacy.sections[0].blade_angle
    assert legacy.diffuser_profile.thickness is not legacy.sections[0].thickness
    legacy.diffuser_profile.blade_angle.points[1].value=12
    assert legacy.sections[0].blade_angle.points[1].value==62

def test_invalid_diffuser_profile_does_not_write(tmp_path):
    p=BladeParameters();p.diffuser_profile.thickness.points[1].value=-1
    with pytest.raises(ValueError):save_project(tmp_path/"invalid.json",p)
    assert not (tmp_path/"invalid.json").exists()
