"""Service extraction checks, separate from historical numerical fixtures."""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from blade_designer.fileio.project_io import load_project
from blade_designer.geometry import preview_computation as service
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.geometry.flow_area import calculate_flow_area
from blade_designer.geometry.row_domain import preview_wall_chunks
from blade_designer.models.blade_rows import initial_rows, row_parameters
from blade_designer.models.parameters import BladeParameters


ROOT = Path(__file__).resolve().parents[1]


def assert_exact(actual, expected):
    if isinstance(expected, np.ndarray):
        np.testing.assert_array_equal(actual, expected)
    elif is_dataclass(expected):
        assert type(actual) is type(expected)
        for field in fields(expected):
            assert_exact(getattr(actual, field.name), getattr(expected, field.name))
    elif isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_exact(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        assert type(actual) is type(expected) and len(actual) == len(expected)
        for a, b in zip(actual, expected):
            assert_exact(a, b)
    else:
        assert actual == expected


@pytest.mark.parametrize("identifier", ["row-1", "row-2", "row-3"])
def test_selected_default_rows_match_existing_engines_exactly(identifier):
    project = load_project(ROOT / "blade_designer/defaults/default_project.json")
    row = next(row for row in project.blade_rows if row.identifier == identifier)
    params = row_parameters(project, row)
    before = deepcopy(params)
    designer = BladeDesigner()
    expected = (designer.generate_3d(params) if row.kind == "impeller"
                else designer.generate_diffuser_3d(params))
    area = calculate_flow_area(expected.hub, expected.shroud, params.flow_path,
        points=params.resolution.area_points, strict=False, mean_points=params.resolution.mean_points)
    result = service.prepare_preview(params, row.kind, include_legacy=True)
    assert result.selected_error is None
    assert_exact(result.impeller if row.kind == "impeller" else result.diffuser, expected)
    assert_exact(result.area, area)
    try:
        legacy = designer.generate_diffuser(params)
    except (ValueError, ArithmeticError) as exc:
        assert result.legacy is None and result.legacy_error == str(exc)
    else:
        assert result.legacy_error is None
        assert_exact(result.legacy, legacy)
    if row.name == "RC":
        assert expected.sections[0].camber.r[0] > expected.sections[0].camber.r[-1]
    assert params == before


def test_all_default_rows_and_analysis_walls_match_original_sequence():
    params = load_project(ROOT / "blade_designer/defaults/default_project.json")
    before = deepcopy(params)
    expected = []
    chunks = []
    designer = BladeDesigner()
    for row in params.blade_rows:
        p = row_parameters(params, row)
        g = designer.generate_3d(p) if row.kind == "impeller" else designer.generate_diffuser_3d(p)
        expected.append((row.identifier, row.name, g, p.geometry.vane_count))
        chunks.extend(preview_wall_chunks(p, g, row.identifier).get("analysis_shroud", []))
    result = service.prepare_row_previews(params)
    assert not result.errors
    assert_exact(result.entries, expected)
    assert_exact(result.analysis_chunks, chunks)
    assert params == before


class StubDesigner:
    def __init__(self, fail=()):
        self.fail = fail
        self.calls = []
        self.wall = SimpleNamespace(hub=object(), shroud=object())
        self.legacy = object()

    def generate_diffuser(self, params):
        return self._run("legacy", self.legacy)

    def generate_3d(self, params):
        return self._run("impeller", self.wall)

    def generate_diffuser_3d(self, params):
        return self._run("diffuser", self.wall)

    def _run(self, kind, result):
        self.calls.append(kind)
        if kind in self.fail:
            raise ArithmeticError(kind + " unavailable")
        return result


@pytest.fixture
def area_stub(monkeypatch):
    marker = object()
    monkeypatch.setattr(service, "calculate_flow_area", lambda *args, **kwargs: marker)
    return marker


def test_valid_stator_survives_legacy_and_reference_failures(area_stub):
    designer = StubDesigner(("legacy", "impeller"))
    result = service.prepare_preview(BladeParameters(), "diffuser", include_legacy=True, designer=designer)
    assert designer.calls == ["legacy", "diffuser", "impeller"]
    assert result.diffuser is designer.wall and result.area is area_stub
    assert result.legacy is None and result.impeller is None and result.selected_error is None
    assert result.legacy_error == "legacy unavailable" and result.reference_error == "impeller unavailable"


@pytest.mark.parametrize("kind", ["impeller", "diffuser"])
def test_selected_failure_retains_valid_legacy_for_controller(kind, area_stub):
    designer = StubDesigner((kind,))
    result = service.prepare_preview(BladeParameters(), kind, include_legacy=True, designer=designer)
    assert result.legacy is designer.legacy and result.legacy_error is None
    assert result.selected_error == kind + " unavailable" and result.area is None
    assert designer.calls == ["legacy", kind]


def test_precomputed_impeller_and_injected_designer_are_reused(area_stub):
    designer = StubDesigner(("impeller", "legacy"))
    result = service.prepare_preview(BladeParameters(), "impeller", designer=designer, impeller=designer.wall)
    assert result.impeller is designer.wall and result.area is area_stub
    assert designer.calls == [] and result.selected_error is None


def test_area_failure_is_selected_failure_without_discarding_legacy(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ValueError("area unavailable")
    monkeypatch.setattr(service, "calculate_flow_area", unavailable)
    designer = StubDesigner()
    result = service.prepare_preview(BladeParameters(), "impeller", include_legacy=True, designer=designer)
    assert result.selected_error == "area unavailable" and result.area is None
    assert result.legacy is designer.legacy


def test_programming_errors_are_not_reported_as_invalid_geometry(monkeypatch):
    designer = StubDesigner()
    def broken(params):
        raise RuntimeError("programming error")
    monkeypatch.setattr(designer, "generate_3d", broken)
    with pytest.raises(RuntimeError, match="programming error"):
        service.prepare_preview(BladeParameters(), "impeller", designer=designer)


def test_unknown_target_rejected_before_engine_or_input_access():
    with pytest.raises(ValueError, match="Unknown preview row type"):
        service.prepare_preview(None, "unknown")


def test_service_owns_parameter_copy(area_stub):
    params = BladeParameters()
    before = deepcopy(params)
    designer = StubDesigner()
    original = designer.generate_3d
    def mutate(p):
        p.geometry.vane_count += 1
        return original(p)
    designer.generate_3d = mutate
    assert service.prepare_preview(params, "impeller", designer=designer).selected_error is None
    assert params == before


@pytest.mark.parametrize("failure", ["geometry", "wall"])
def test_failed_row_and_wall_chunks_are_omitted_together(monkeypatch, failure):
    params = BladeParameters()
    params.blade_rows = initial_rows(params)
    before = deepcopy(params)
    designer = StubDesigner(("diffuser",) if failure == "geometry" else ())
    chunk = object()
    def walls(p, g, identifier):
        if identifier == "row-2":
            raise ValueError("wall unavailable")
        return {"analysis_shroud": [chunk]}
    monkeypatch.setattr(service, "preview_wall_chunks", walls)
    result = service.prepare_row_previews(params, designer=designer)
    assert [(i, n, count) for i, n, g, count in result.entries] == [
        ("row-1", "Impeller", params.geometry.vane_count)]
    assert result.analysis_chunks == [chunk]
    assert len(result.errors) == 1 and "3D Diffuser" in result.errors[0] and "row omitted" in result.errors[0]
    assert params == before


def test_core_runs_in_fresh_process_without_qt_or_cad():
    code = """
import sys
from blade_designer.geometry.preview_computation import prepare_preview
from blade_designer.models.parameters import BladeParameters
r = prepare_preview(BladeParameters(), 'impeller')
assert r.selected_error is None and r.area is not None
assert not any(k.startswith(('PySide6', 'pyqtgraph', 'OCP')) for k in sys.modules)
"""
    completed = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
