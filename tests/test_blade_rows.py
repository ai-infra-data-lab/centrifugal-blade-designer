import json
from copy import deepcopy
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.blade_rows import initial_rows, row_parameters
from blade_designer.fileio.project_io import save_project, load_project


def project():
    params = BladeParameters()
    params.blade_rows = initial_rows(params)
    params.active_blade_row = "row-1"
    return params


def test_row_roundtrip_and_shared_walls(tmp_path):
    params = project()
    params.blade_rows[1].parameters.geometry.vane_count = 13
    params.blade_rows[1].parameters.diffuser_profile.thickness.points[1].value = 6
    params.hub.start_z += 2
    materialized = row_parameters(params, params.blade_rows[1])
    assert materialized.hub == params.hub
    assert materialized.hub is not params.hub
    assert materialized.geometry.vane_count == 13
    assert params.blade_rows[0].parameters.geometry.vane_count == 20
    path = tmp_path / "rows.json"
    save_project(path, params)
    assert load_project(path) == params


@pytest.mark.parametrize("invalid", ["duplicate", "kind", "active", "nested", "empty", "inactive_geometry"])
def test_invalid_rows_rejected_before_write(tmp_path, invalid):
    params = project()
    if invalid == "duplicate":
        params.blade_rows[1].identifier = "row-1"
    elif invalid == "kind":
        params.blade_rows[0].kind = "unknown"
    elif invalid == "active":
        params.active_blade_row = "missing"
    elif invalid == "nested":
        params.blade_rows[0].parameters.blade_rows = []
    elif invalid == "empty":
        params.blade_rows = []
    else:
        params.blade_rows[1].parameters.geometry.vane_count = 0
    with pytest.raises(ValueError):
        save_project(tmp_path / "invalid.json", params)
    assert not (tmp_path / "invalid.json").exists()


def test_legacy_payload_unchanged_and_malformed_rows_rejected(tmp_path):
    path = tmp_path / "legacy.json"
    params = BladeParameters()
    save_project(path, params)
    data = json.loads(path.read_text())
    assert "blade_rows" not in data and "active_blade_row" not in data
    assert load_project(path) == params
    before = deepcopy(data)
    data["blade_rows"] = [{"name": "Incomplete"}]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_project(path)
    assert before["geometry"] == params.geometry.__dict__
