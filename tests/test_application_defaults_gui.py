import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
from pathlib import Path
import hashlib
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from main import create_window, parse_arguments
from blade_designer.fileio.project_io import load_project, save_project


TEMPLATE = Path(__file__).resolve().parents[1] / "blade_designer/defaults/default_project.json"


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = create_window(parse_arguments([])); w.show(); QTest.qWait(50)
    yield w
    w.timer.stop(); w.close(); w.deleteLater(); app.processEvents()


def test_startup_and_new_use_independent_template(window):
    w = window
    expected = load_project(TEMPLATE)
    digest = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    assert expected.sections[0].blade_angle.points[0].value == pytest.approx(50.70160218229253)
    assert w.get_parameters() == expected
    assert w.project_path is None and w.undo_stack.count() == 0
    w.blade_count.setValue(13); w.blade_count.editingFinished.emit(); w.update_geometry()
    assert w.get_parameters().geometry.vane_count == 13
    w.new_project()
    assert w.get_parameters() == expected
    assert w.project_path is None and w.undo_stack.count() == 0
    assert hashlib.sha256(TEMPLATE.read_bytes()).hexdigest() == digest


def test_visible_blade_count_is_per_row_with_undo_save_and_annulus(window, tmp_path):
    w = window
    assert w.blade_count_widget.isVisible()
    original = deepcopy(w.get_parameters())
    w.annulus_2d.setChecked(True); w.annulus_3d.setChecked(True)
    w.blade_count.setValue(13); w.blade_count.editingFinished.emit(); w.update_geometry()
    assert w.annulus_plot.vane_count == 13 and w.model_preview_3d.blade_count == 13
    w.undo()
    assert w.get_parameters() == original
    w.redo(); assert w.blade_count.value() == 13
    w.select_blade_row("row-2"); assert w.blade_count.value() == 20
    w.blade_count.setValue(17); w.blade_count.editingFinished.emit(); w.update_geometry()
    assert w.annulus_plot.vane_count == 17 and w.model_preview_3d.blade_count == 17
    w.select_blade_row("row-1"); assert w.blade_count.value() == 13
    path = tmp_path / "counts.json"
    w.save_to_path(path)
    assert [r.parameters.geometry.vane_count for r in load_project(path).blade_rows] == [13,17]
    w.new_project(); w.load_from_path(path)
    assert w.blade_count.value() == 13
    w._select_meridional(); assert not w.blade_count_widget.isVisible()
    w.select_blade_row("row-2"); assert w.blade_count_widget.isVisible() and w.blade_count.value() == 17


def test_explicit_project_overrides_startup_and_new_restores_template(window, tmp_path):
    w = window; params = load_project(TEMPLATE)
    params.geometry.vane_count = params.blade_rows[0].parameters.geometry.vane_count = 7
    path = tmp_path / "explicit.json"; save_project(path, params)
    other = create_window(parse_arguments(["--project", str(path)]))
    try:
        assert other.blade_count.value() == 7 and other.project_path == path
        other.new_project()
        assert other.get_parameters() == load_project(TEMPLATE)
    finally:
        other.timer.stop(); other.close(); other.deleteLater()
