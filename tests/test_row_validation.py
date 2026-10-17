"""Selected 3D inputs versus strict legacy/project acceptance; no repair."""
from copy import deepcopy
import json
import numpy as np
import pytest

from blade_designer.models.parameters import BladeParameters, SplitterParameters, TipClearanceParameters, ImpellerTrimParameters
from blade_designer.models.validation import validate_parameters, validate_row_settings, ValidationLevel
from blade_designer.geometry.geometry_3d import generate_impeller, generate_diffuser_3d
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.fileio.project_io import save_project, load_project


GENERATORS = {"impeller": generate_impeller, "diffuser": generate_diffuser_3d}


def break_unused(p, kind, field):
    if field == "radial":
        p.geometry.r_le = -5
        p.geometry.r_te = -10
    elif field == "other_edges":
        other = p.diffuser_edges if kind == "impeller" else p.impeller_edges
        other.trailing_edge.hub_m_flow_norm = 0
    elif field == "other_profile":
        other = p.diffuser_profile if kind == "impeller" else p.sections[0]
        other.thickness.points[0].value = -1
        other.edge_parameters.le_type = "invalid"
    elif field == "rake":
        p.impeller_te_rake_deg = 90
    elif field == "trim":
        p.impeller_trim = ImpellerTrimParameters(shroud_area_cut_percent=100)
    elif field == "clearance":
        p.tip_clearance = TipClearanceParameters(-1, 0)
    elif field == "splitter":
        p.splitter = SplitterParameters(pitch_fraction=0)


@pytest.mark.parametrize("kind,field", [
    (kind, field) for kind in GENERATORS for field in ("radial", "other_edges", "other_profile")
] + [("diffuser", field) for field in ("rake", "trim", "clearance", "splitter")])
def test_unused_values_do_not_change_any_selected_master_coordinate(kind, field):
    p = BladeParameters()
    expected = GENERATORS[kind](p)
    break_unused(p, kind, field)
    before = deepcopy(p)
    actual = GENERATORS[kind](p)
    assert p == before
    for a, b in zip(actual.sections, expected.sections):
        for role in ("camber", "master_le", "master_ps", "master_te", "master_ss"):
            np.testing.assert_array_equal(getattr(a, role).xyz, getattr(b, role).xyz)
    if field == "radial":
        assert any(i.level == ValidationLevel.ERROR for i in validate_parameters(p))
        with pytest.raises(ValueError):
            BladeDesigner().generate_diffuser(p)


@pytest.mark.parametrize("kind", GENERATORS)
@pytest.mark.parametrize("field", ["theta", "count", "rotation", "mapping", "points", "precision",
                                   "profile_angle", "profile_thickness", "profile_edge", "edges", "wall"])
def test_used_invalid_values_still_reject_without_mutation(kind, field):
    p = BladeParameters()
    profile = p.sections[-1] if kind == "impeller" else p.diffuser_profile
    edges = p.impeller_edges if kind == "impeller" else p.diffuser_edges
    if field == "theta": p.geometry.theta_le_deg = float("inf")
    elif field == "count": p.geometry.vane_count = True
    elif field == "rotation": p.rotation_direction = "CW"
    elif field == "mapping": p.surface_mapping = "invalid"
    elif field == "points": p.output_points.ps_points = 1
    elif field == "precision": p.export.significant_digits = 0
    elif field == "profile_angle": profile.blade_angle.points[0].value = 85
    elif field == "profile_thickness": profile.thickness.points[0].value = -1
    elif field == "profile_edge": profile.edge_parameters.le_ellipse_ratio = 0
    elif field == "edges": edges.trailing_edge.hub_m_flow_norm = 0
    elif field == "wall": p.hub.segments[0].length = -1
    before = deepcopy(p)
    with pytest.raises(ValueError): GENERATORS[kind](p)
    assert p == before


@pytest.mark.parametrize("field", ["rake", "trim", "clearance", "splitter"])
def test_impeller_options_remain_mandatory_for_impeller(field):
    p = BladeParameters()
    break_unused(p, "diffuser", field)
    with pytest.raises(ValueError): generate_impeller(p)


@pytest.mark.parametrize("field", ["radial", "other_edges", "other_profile", "rake", "trim", "clearance", "splitter"])
def test_project_load_save_remain_strict_and_protect_existing_file(tmp_path, field):
    path = tmp_path / "project.json"
    p = BladeParameters()
    save_project(path, p)
    original = path.read_bytes()
    break_unused(p, "diffuser", field)
    # A valid selected stator does not authorize saving an invalid whole project.
    generate_diffuser_3d(p)
    with pytest.raises(ValueError): save_project(path, p)
    assert path.read_bytes() == original
    data = json.loads(original)
    if field == "radial": data["geometry"]["r_le"] = -5
    elif field == "other_edges": data["impeller_edges"]["trailing_edge"]["hub_m_flow_norm"] = 0
    elif field == "other_profile": data["sections"][0]["thickness"]["points"][0]["value"] = -1
    elif field == "rake": data["impeller_te_rake_deg"] = 90
    elif field == "trim": data["impeller_trim"] = {"shroud_area_cut_percent": 100, "diameter_mode": "off", "diameter_mm": 0, "diameter_cut_percent": 0}
    elif field == "clearance": data["tip_clearance"] = {"le_mm": -1, "te_mm": 0}
    elif field == "splitter": data["splitter"] = {"hub_start_fraction": .5, "tip_start_fraction": .5, "pitch_fraction": 0, "thickness_scale": 1, "sections": None}
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError): load_project(invalid)


def test_project_still_rejects_unused_diffuser_edges(tmp_path):
    p = BladeParameters()
    break_unused(p, "impeller", "other_edges")
    generate_impeller(p)
    with pytest.raises(ValueError): save_project(tmp_path / "invalid.json", p)


def test_unknown_row_kind_is_not_silently_treated_as_stator():
    with pytest.raises(ValueError, match="kind"):
        validate_row_settings(BladeParameters(), "unknown")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -.01, 1.01])
def test_stator_also_preserves_unused_edge_data_integrity(value):
    p = BladeParameters()
    p.impeller_edges.leading_edge.hub_m_flow_norm = value
    with pytest.raises(ValueError, match="Blade edge positions"):
        generate_diffuser_3d(p)
