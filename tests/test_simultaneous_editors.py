import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt, QEvent, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from main import parse_arguments


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); QTest.qWait(30)
    yield w
    for child in w._optimization_windows:
        child.timer.stop(); child.close(); child.deleteLater()
    w.timer.stop(); w.close(); w.deleteLater(); app.processEvents()


@pytest.mark.parametrize("attribute", ["angle_editor", "thickness_editor"])
def test_both_tables_edit_without_section_switch_and_roundtrip(window, attribute, tmp_path):
    w = window; editor = getattr(w, attribute)
    w.tabs.setCurrentWidget(editor)
    assert all(editor.series[span].table.isVisible() for span in (0, 1))
    before = deepcopy(w.get_parameters())
    for span, value in ((0, 47 if attribute == "angle_editor" else 5),
                        (1, 39 if attribute == "angle_editor" else 7)):
        box = editor.series[span].table.cellWidget(1, 1)
        box.setValue(value); box.editingFinished.emit()
    assert w.section_selector.combo.currentIndex() == 0
    w.update_geometry()
    after = w.get_parameters()
    assert after.diffuser_profile == before.diffuser_profile
    field = "blade_angle" if attribute == "angle_editor" else "thickness"
    for section in w.impeller_geometry.sections:
        values = section.beta_m_deg if field == "blade_angle" else section.thickness
        np.testing.assert_array_equal(editor.series[section.span].curve.yData, values)
    w.save_to_path(tmp_path / "both.json")
    w.undo(); assert getattr(w.get_parameters().sections[1], field) == getattr(before.sections[1], field)
    w.redo(); assert w.get_parameters() == after
    w.new_project(); w.load_from_path(tmp_path / "both.json")
    assert w.get_parameters() == after


@pytest.mark.parametrize("attribute", ["angle_editor", "thickness_editor"])
@pytest.mark.parametrize("span", [0, 1])
def test_coincident_hub_tip_handles_can_both_be_dragged(window, attribute, span):
    w = window; app = QApplication.instance(); editor = getattr(w, attribute)
    w.tabs.setCurrentWidget(editor); w.fit_view(); QTest.qWait(100)
    p = editor.series[span].get_points()[1]
    plot = editor.plot; viewport = plot.viewport()
    start = plot.mapFromScene(plot.getViewBox().mapViewToScene(QPointF(p.m_norm, p.value)))
    # Hub center and Tip outer ring remain individually reachable at identical coordinates.
    if span == 1: start += QPoint(9, 0)
    finish = start + QPoint(24, -14)
    before = deepcopy(w.get_parameters()); count = w.undo_stack.count()
    ranges = np.array(plot.getViewBox().viewRange())
    QTest.mouseMove(viewport, start); QTest.qWait(30)
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 6):
        pos = start + (finish - start) * step / 5
        event = QMouseEvent(QEvent.Type.MouseMove, QPointF(pos), QPointF(viewport.mapToGlobal(pos)),
                           Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        app.sendEvent(viewport, event); app.processEvents(); QTest.qWait(20)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, finish)
    QTest.qWait(200)
    after = w.get_parameters()
    assert after.sections[int(span)] != before.sections[int(span)]
    assert after.sections[1-int(span)] == before.sections[1-int(span)]
    assert w.undo_stack.count() == count + 1
    np.testing.assert_allclose(plot.getViewBox().viewRange(), ranges)
    assert w.section_selector.combo.currentIndex() == 0
    w.undo(); assert w.get_parameters() == before
    w.redo(); assert w.get_parameters() == after


def test_normal_editor_and_independent_optimization_startup(window):
    w = window
    tabs = [w.tabs.tabText(i) for i in range(w.tabs.count())]
    assert "Diffuser Geometry" not in tabs and "Optimization" not in tabs
    assert w.optimization_widget is None
    before = deepcopy(w.get_parameters())
    other = w.open_optimization_mode()
    assert other.mode == "optimization" and other.optimization_widget is not None
    assert other.tabs.tabText(other.tabs.currentIndex()) == "Optimization"
    other.angle_editor.table.cellWidget(1, 1).setValue(43); other.commit_edit()
    assert other.get_parameters().diffuser_profile != before.diffuser_profile
    assert w.get_parameters() == before and w.undo_stack.count() == 0
    assert parse_arguments([]).mode == "design"
    options = parse_arguments(["--mode", "optimization", "--project", "example.json"])
    assert options.mode == "optimization" and options.project == "example.json"


def test_target_controls_and_intermediate_profiles(window):
    w = window
    w.add_span_section(.5)
    assert list(w.angle_editor.series) == [0, .5, 1]
    assert all(e.plot is w.angle_editor.plot for e in w.angle_editor.series.values())
    w.view_mode.setCurrentIndex(1)
    assert list(w.angle_editor.series) == [0]
    assert w.angle_editor.legend.items[0][1].text == "Diffuser"
    assert w.panel.groups["Geometry"].layout().isRowVisible(w.panel.controls["r_le"])
    w.view_mode.setCurrentIndex(0)
    assert list(w.angle_editor.series) == [0, .5, 1]
    assert not w.panel.groups["Geometry"].layout().isRowVisible(w.panel.controls["r_le"])
