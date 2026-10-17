import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import json
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.fileio.project_io import save_project, load_project
from test_row_project_validation import single_row
from test_standard_menus_gui import dispose


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = MainWindow(mode="optimization")
    w.timer.stop()
    yield w
    dispose(w, app)


@pytest.mark.parametrize("unused", ["radial", "impeller_shape", "other_edges"])
def test_stator_load_edit_save_reload_without_unused_engine_gate(window, tmp_path, unused):
    w = window
    p = single_row(unused=unused)
    source = tmp_path / "source.json"
    save_project(source, p)
    original = source.read_bytes()
    w.load_from_path(source)
    assert w.get_parameters() == p and w.undo_stack.count() == 0
    assert w._editing_target == 1 and w.row_metrics_widget.source.row_name == "RC"
    assert w._selected_3d_geometry is w.diffuser_geometry
    expected = w.diffuser_geometry.sections[0].master_ps.xyz.copy()
    if unused == "radial":
        assert w.optimization_widget.baseline is None
        assert w.optimization_widget.baseline_source is None
        assert w.optimization_widget.candidate_source is None
        assert not w.optimization_widget.preview_button.isEnabled()
        assert not w.optimization_widget.apply_button.isEnabled()
        w.optimization_widget.mode.setCurrentIndex(1)
        w.optimization_widget.preview_candidate()
        assert w.optimization_widget.last_result is None
        assert "unavailable" in w.optimization_widget.report.toPlainText()
    if unused != "radial": assert w.impeller_geometry is None
    saved = tmp_path / "saved.json"
    w.save_to_path(saved)
    assert load_project(saved) == p and source.read_bytes() == original
    w.load_from_path(saved)
    np.testing.assert_array_equal(w.diffuser_geometry.sections[0].master_ps.xyz, expected)
    # A normal design edit is still recorded and persisted in the correct row.
    w.angle_editor.move_point(1, .3, 35)
    w.commit_edit();w.update_geometry()
    changed = deepcopy(w.get_parameters())
    assert changed != p and w.undo_stack.count() > 0
    w.save_to_path(saved);w.load_from_path(saved)
    assert w.get_parameters() == changed and w.undo_stack.count() == 0


def test_loading_valid_design_restores_cleared_legacy_optimization(window, tmp_path):
    w = window
    path = tmp_path / "project.json"
    save_project(path, single_row())
    w.load_from_path(path)
    assert w.optimization_widget.baseline is None
    w.new_project()
    assert w.optimization_widget.baseline is not None
    assert w.optimization_widget.baseline_source is not None
    assert w.optimization_widget.preview_button.isEnabled()


def test_invalid_loaded_row_does_not_replace_gui_history_path_or_current_model(window, tmp_path):
    w = window
    w.angle_editor.move_point(1, .3, 35);w.commit_edit();w.update_geometry()
    before = deepcopy(w.get_parameters())
    history = (w.undo_stack.count(), w.undo_stack.index())
    path_before = w.project_path
    geometry = w._selected_3d_geometry
    camera = deepcopy(w.model_preview_3d.camera_position)
    path = tmp_path / "invalid.json"
    save_project(path, single_row())
    data = json.loads(path.read_text(encoding="utf-8"))
    data["blade_rows"][0]["parameters"]["diffuser_edges"]["trailing_edge"]["hub_m_flow_norm"] = .1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError): w.load_from_path(path)
    assert w.get_parameters() == before and w.project_path == path_before
    assert (w.undo_stack.count(), w.undo_stack.index()) == history
    assert w._selected_3d_geometry is geometry
    for key, value in camera.items():
        np.testing.assert_array_equal(w.model_preview_3d.camera_position[key], value)
