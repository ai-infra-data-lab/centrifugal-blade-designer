"""Multi-row persistence uses declared physical geometry, preserving legacy files."""
from copy import deepcopy
import json
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters, BladeRow
from blade_designer.models.blade_rows import row_snapshot, row_parameters, initial_rows
from blade_designer.fileio.project_io import save_project, load_project
from blade_designer.geometry.geometry_3d import generate_impeller, generate_diffuser_3d
from blade_designer.geometry.designer import BladeDesigner


def single_row(kind="diffuser", unused="radial"):
    p = BladeParameters()
    if unused == "radial":
        p.geometry.r_le = 145.12345678901234
        p.geometry.r_te = 105.98765432109876
    elif unused == "impeller_shape":
        p.sections[-1].thickness.points[1].value = 500
    elif unused == "other_edges":
        edges = p.impeller_edges if kind == "diffuser" else p.diffuser_edges
        edges.trailing_edge.hub_m_flow_norm = .05
    p.blade_rows = [BladeRow("only-row", "RC" if kind == "diffuser" else "Rotor", kind, row_snapshot(p))]
    p.active_blade_row = "only-row"
    return p


@pytest.mark.parametrize("kind,unused", [("impeller", "radial"), ("impeller", "other_edges"),
                                         ("diffuser", "radial"), ("diffuser", "other_edges"),
                                         ("diffuser", "impeller_shape")])
def test_roundtrip_preserves_unused_values_and_every_actual_master_point(tmp_path, kind, unused):
    p = single_row(kind, unused)
    generate = generate_impeller if kind == "impeller" else generate_diffuser_3d
    before = deepcopy(p)
    expected = generate(row_parameters(p, p.blade_rows[0]))
    path = tmp_path / "rows.json"
    save_project(path, p)
    saved = path.read_bytes()
    restored = load_project(path)
    assert path.read_bytes() == saved and restored == before and p == before
    assert json.loads(saved)["schema_version"] == "0.3"
    actual = generate(row_parameters(restored, restored.blade_rows[0]))
    for a, b in zip(expected.sections, actual.sections):
        for role in ("camber", "master_le", "master_ps", "master_te", "master_ss"):
            np.testing.assert_array_equal(getattr(a, role).xyz, getattr(b, role).xyz)
    if unused == "radial":
        with pytest.raises(ValueError): BladeDesigner().generate_diffuser(restored)
    if unused == "impeller_shape":
        with pytest.raises(ValueError): generate_impeller(restored)


@pytest.mark.parametrize("kind", ["impeller", "diffuser"])
def test_inactive_declared_row_must_be_valid_in_its_own_kind(tmp_path, kind):
    p = BladeParameters()
    p.blade_rows = initial_rows(p)
    bad = next(r for r in p.blade_rows if r.kind == kind)
    p.active_blade_row = next(r.identifier for r in p.blade_rows if r is not bad)
    bad.name = "Invalid inactive row"
    if kind == "impeller": bad.parameters.sections[-1].thickness.points[1].value = 500
    else: bad.parameters.diffuser_edges.trailing_edge.hub_m_flow_norm = .1
    target = tmp_path / "existing.json"
    target.write_bytes(b"original project")
    with pytest.raises(ValueError, match="Invalid inactive row"):
        save_project(target, p)
    assert target.read_bytes() == b"original project"


@pytest.mark.parametrize("target", ["root", "row"])
@pytest.mark.parametrize("invalid", ["radius", "nan", "angle", "edge_bound", "gap", "span", "curve", "axis", "profile_type", "empty_sections"])
def test_unused_stored_value_constraints_and_existing_file_protection(tmp_path, target, invalid):
    p = single_row()
    q = p if target == "root" else p.blade_rows[0].parameters
    if invalid == "radius": q.geometry.r_le = -1
    elif invalid == "nan": q.geometry.r_te = float("nan")
    elif invalid == "angle": q.sections[-1].blade_angle.points[0].value = 85
    elif invalid == "edge_bound": q.impeller_edges.leading_edge.hub_m_flow_norm = 1.01
    elif invalid == "gap":
        from blade_designer.models.parameters import TipClearanceParameters
        q.tip_clearance = TipClearanceParameters(-1, 0)
    elif invalid == "span": q.sections[-1].span = .5
    elif invalid == "curve": q.shroud.start_r = -1
    elif invalid == "axis": q.turbogrid.rotation_axis = "invalid"
    elif invalid == "profile_type": q.diffuser_profile = None
    elif invalid == "empty_sections": q.sections = []
    path = tmp_path / "preserved.json"
    path.write_bytes(b"preserve")
    with pytest.raises(ValueError): save_project(path, p)
    assert path.read_bytes() == b"preserve"


@pytest.mark.parametrize("target", ["root", "row"])
@pytest.mark.parametrize("invalid", ["radius", "nan", "profile", "edges", "shape", "nested"])
def test_load_rejects_malformed_or_used_invalid_geometry_without_rewriting(tmp_path, target, invalid):
    path = tmp_path / "bad.json"
    save_project(path, single_row())
    data = json.loads(path.read_text(encoding="utf-8"))
    q = data if target == "root" else data["blade_rows"][0]["parameters"]
    if invalid == "radius": q["geometry"]["r_te"] = -1
    elif invalid == "nan": q["sections"][-1]["thickness"]["points"][0]["value"] = float("nan")
    elif invalid == "profile": q["diffuser_profile"]["span"] = 1
    elif invalid == "edges": q["diffuser_edges"]["trailing_edge"]["hub_m_flow_norm"] = .1
    elif invalid == "shape": q["diffuser_profile"]["thickness"]["points"][1]["value"] = 500
    elif invalid == "nested":
        if target == "root": q["active_blade_row"] = "missing"
        else: q["blade_rows"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError): load_project(path)
    assert path.read_bytes() == before


def test_no_row_legacy_still_rejects_reversed_radial_extent(tmp_path):
    p = single_row()
    p.blade_rows = None;p.active_blade_row = None
    with pytest.raises(ValueError): save_project(tmp_path / "legacy.json", p)


def test_failed_replace_preserves_valid_multirow_project(tmp_path, monkeypatch):
    path = tmp_path / "project.json"
    p = single_row()
    save_project(path, p)
    original = path.read_bytes()
    p.geometry.vane_count += 1
    def unavailable(*args):raise OSError("replace blocked")
    monkeypatch.setattr("blade_designer.fileio.project_io.os.replace", unavailable)
    with pytest.raises(OSError, match="replace blocked"): save_project(path, p)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
