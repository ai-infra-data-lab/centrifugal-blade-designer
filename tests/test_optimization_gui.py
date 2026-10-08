import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import EdgeType
from blade_designer.optimization.models import OptimizationMode


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


@pytest.fixture
def window(app):
    w = MainWindow(mode="optimization")
    w.show()
    app.processEvents()
    yield w
    w.timer.stop()
    w.close()
    w.deleteLater()
    app.processEvents()


def test_default_preview_and_le_location(window):
    o = window.optimization_widget
    assert len(o.rows) == 9
    assert o.baseline == window.get_parameters()
    assert "WARNING" not in window.statusBar().currentMessage()
    o.preview_button.click()
    assert o.last_result.feasible and o.apply_button.isEnabled()
    assert "edge location is allowed" in o.report.toPlainText()
    assert window.geometry.metrics.throat.width == pytest.approx(o.last_result.geometry.metrics.throat.width)


def test_apply_and_baseline_stays_fixed(window):
    o = window.optimization_widget
    baseline = o.baseline
    row = next(row for row in o.rows if row["parameter"].name == "beta_te")
    row["initial"].setValue(-1.)
    o.preview_button.click()
    assert o.last_result.feasible
    o.apply_button.click()
    assert window.get_parameters().diffuser_profile.blade_angle.points[-1].value == 49.
    assert window.get_parameters().sections[0].blade_angle.points[-1].value == 50.
    assert o.baseline == baseline
    row["initial"].setValue(-2.)
    assert o.last_result is None and not o.apply_button.isEnabled()
    o.apply_button.click()
    assert window.get_parameters().diffuser_profile.blade_angle.points[-1].value == 49.
    assert window.get_parameters().sections[0].blade_angle.points[-1].value == 50.


def test_rejection_does_not_apply(window):
    o = window.optimization_widget
    before = window.get_parameters()
    use,value = o.constraint_controls["minimum_throat"]
    value.setValue(100.)
    o.preview_button.click()
    assert not o.last_result.feasible
    assert not o.apply_button.isEnabled()
    assert "REJECTED" in o.report.toPlainText()
    o.apply_candidate()
    assert window.get_parameters() == before


def test_capture_presets_and_architecture(window):
    o = window.optimization_widget
    window.panel.controls["r_te"].setValue(170)
    assert o.baseline.geometry.r_te == 160
    o.capture_button.click()
    assert o.baseline.geometry.r_te == 170
    o.preset.setCurrentIndex(1)
    assert len(o.rows) == 7
    o.mode.setCurrentIndex(1)
    assert len(o.rows) == 10
    vane = next(row for row in o.rows if row["parameter"].name == "vane_count")
    assert vane["type"].currentData() == "discrete"
    vane["initial"].setValue(19)
    o.preview_button.click()
    assert o.last_result is not None and o.last_result.design.geometry.vane_count == 19


def test_ellipse_variable_and_invalid_configuration(window):
    o = window.optimization_widget
    window.view_mode.setCurrentIndex(1)
    le = window.panel.controls["le_type"]
    le.setCurrentIndex(le.findData(EdgeType.ELLIPTICAL))
    o.capture_button.click()
    ratio = next(row for row in o.rows if row["parameter"].name == "le_ellipse_ratio")
    assert ratio["enabled"].isChecked()
    ratio["initial"].setValue(1.5)
    o.preview_button.click()
    assert o.last_result.feasible
    assert o.last_result.design.edges.le_ellipse_ratio == 1.5
    ratio["lower"].setValue(2.)
    o.preview_button.click()
    assert o.last_result is None
    assert "Configuration error" in o.report.toPlainText()
    assert not o.apply_button.isEnabled()


def test_load_resets_optimization_baseline(window,tmp_path):
    o = window.optimization_widget
    window.panel.controls["r_te"].setValue(175)
    window.save_to_path(tmp_path/"blade.json")
    window.load_from_path(tmp_path/"blade.json")
    assert o.baseline.geometry.r_te == 175
    window.new_project()
    assert o.baseline.geometry.r_te == 160
