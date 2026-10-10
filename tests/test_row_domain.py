import json
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.blade_rows import initial_rows
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.meridional_segments import sample_meridional
from blade_designer.geometry.row_domain import wall_interval
from blade_designer.fileio.project_io import save_project, load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid


def assigned_project():
    p = BladeParameters()
    p.impeller_edges.leading_edge.hub_m_flow_norm = .2
    p.impeller_edges.leading_edge.shroud_m_flow_norm = .2
    p.impeller_edges.trailing_edge.hub_m_flow_norm = .4
    p.impeller_edges.trailing_edge.shroud_m_flow_norm = .4
    p.blade_rows = initial_rows(p)
    p.active_blade_row = "row-1"
    for curve in (p.hub, p.shroud):
        for i, segment in enumerate(curve.segments):
            segment.blade_row = "row-1" if i < 2 else "row-2"
    return p


def test_owned_line_and_arc_roundtrip_and_analytic_interval(tmp_path):
    p = assigned_project()
    path = tmp_path / "owned.json"
    save_project(path, p)
    assert load_project(path) == p
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["hub"]["segments"][1]["blade_row"] == "row-1"
    g = generate_impeller(p)
    start, end = wall_interval(p.hub, g.hub, "row-1")
    assert start == 0
    assert end == pytest.approx(25 + 30 * np.pi / 2)
    # Ownership is metadata: the same input geometry must remain identical.
    plain = deepcopy(p)
    for curve in (plain.hub, plain.shroud):
        for segment in curve.segments: segment.blade_row = None
    original = generate_impeller(plain)
    np.testing.assert_array_equal(g.sections[0].camber.xyz, original.sections[0].camber.xyz)


def test_export_crops_only_wall_curves_and_preserves_profile(tmp_path):
    p = assigned_project();p.export.significant_digits = 15
    g = generate_impeller(p)
    files = export_turbogrid(tmp_path / "owned", p)
    for curve, wall, file in zip((p.hub,p.shroud), (g.hub,g.shroud), files[:2]):
        start,end = wall_interval(curve, wall, "row-1")
        actual = np.loadtxt(file)
        endpoints = sample_meridional(wall, np.array([start,end]))
        np.testing.assert_allclose(actual[[0,-1]], np.column_stack((endpoints[:,1],np.zeros(2),endpoints[:,0])), atol=1e-12)
        assert len(actual) == curve.export_points
        assert end < wall.length
    for curve in (p.hub,p.shroud):
        for segment in curve.segments: segment.blade_row = None
    legacy = export_turbogrid(tmp_path / "legacy", p)
    assert files[2].read_bytes() == legacy[2].read_bytes()


@pytest.mark.parametrize("invalid", ["missing_wall", "disconnected", "outside_blade", "outside_profile", "unknown_row", "no_active"])
def test_invalid_domains_do_not_create_or_overwrite_files(tmp_path, invalid):
    p = assigned_project()
    case = tmp_path / "case"
    files = export_turbogrid(case, p)
    before = {file.name: file.read_bytes() for file in files}
    if invalid == "missing_wall":
        for segment in p.shroud.segments: segment.blade_row = None
    elif invalid == "disconnected":
        p.hub.segments[1].blade_row = "row-2";p.hub.segments[2].blade_row = "row-1"
    elif invalid == "outside_blade":
        p.shroud.segments[1].blade_row = "row-2"
    elif invalid == "outside_profile":
        g = generate_impeller(p)
        p.impeller_edges.trailing_edge.shroud_m_flow_norm = wall_interval(p.shroud,g.shroud,"row-1")[1] / g.shroud.length
    elif invalid == "unknown_row": p.hub.segments[0].blade_row = "missing"
    else: p.active_blade_row = None
    with pytest.raises(ValueError): export_turbogrid(case, p)
    assert {file.name: file.read_bytes() for file in files} == before
    with pytest.raises(ValueError): export_turbogrid(tmp_path / "new", p)
    assert not (tmp_path / "new").exists()


def test_unassigned_legacy_json_does_not_gain_segment_keys(tmp_path):
    path = tmp_path / "legacy.json"
    save_project(path, BladeParameters())
    data = json.loads(path.read_text())
    assert set(data["hub"]["segments"][0]) == {"length"}
    assert set(data["hub"]["segments"][1]) == {"radius","sweep_deg","clockwise"}


def test_ownership_without_row_list_is_rejected_before_save(tmp_path):
    p = BladeParameters();p.hub.segments[0].blade_row = "missing"
    with pytest.raises(ValueError, match="requires a blade row list"):
        save_project(tmp_path / "invalid.json", p)
    assert not (tmp_path / "invalid.json").exists()
