import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QLabel
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    QTest.qWait(40)
    yield window
    for dialog in window._tool_dialogs.values():
        dialog.close()
    window.timer.stop()
    window.close()
    window.deleteLater()
    app.processEvents()


def visible_tabs(window):
    return [window.tabs.tabText(i) for i in range(window.tabs.count()) if window.tabs.isTabVisible(i)]


def test_shape_view_is_between_navigator_and_editor(window):
    w = window
    assert w.vertical_splitter.indexOf(w.model_splitter) == 0
    assert w.model_splitter.indexOf(w.central_views) == 0
    assert w.vertical_splitter.widget(1).isAncestorOf(w.tabs)
    assert w.navigator.mapTo(w, w.navigator.rect().center()).x() < w.central_views.mapTo(w, w.central_views.rect().center()).x()
    assert w.central_views.mapTo(w, w.central_views.rect().center()).x() < w.tabs.mapTo(w, w.tabs.rect().center()).x()


def test_station_editor_removed_but_project_stations_and_blade_edges_preserved(window, tmp_path):
    w = window
    saved = w.get_parameters()
    saved.flow_path.stations[1].m_flow_norm = .17
    w.set_parameters(saved)
    w.update_geometry()
    before = deepcopy(w.get_parameters())
    w._select_meridional()
    assert w.meridional_editor.station_table.isHidden()
    assert w.meridional_editor.layout().indexOf(w.meridional_editor.station_table) == -1
    assert w.meridional_editor.context.legend.isHidden()
    assert not any(label.isVisible() and "Component Stations" in label.text()
                   for label in w.meridional_editor.findChildren(QLabel))
    assert w.meridional_editor.blade_edges.isVisible()
    w.meridional_editor.blade_edges.controls["impeller_edges", "leading_edge", "hub"].setValue(.2)
    w.commit_edit()
    assert w.get_parameters().impeller_edges.leading_edge.hub_m_flow_norm == .2
    assert w.get_parameters().flow_path == before.flow_path
    path = tmp_path / "stations-preserved.json"
    w.save_to_path(path)
    w.load_from_path(path)
    assert w.get_parameters().flow_path == before.flow_path
    assert w.get_parameters().impeller_edges.leading_edge.hub_m_flow_norm == .2
    assert w.meridional_editor.station_table.isHidden()


def test_selection_does_not_grow_window_and_central_view_matches_target(window):
    w = window
    before = deepcopy(w.get_parameters())
    size = w.size()
    assert w.frameGeometry().height() <= w.screen().availableGeometry().height()
    assert not w.context_tabs.isVisible()
    for kind in ("row-1", "row-2", "row-1", "row-2"):
        w.navigator.tree.setCurrentItem(w.navigator.meridional_item)
        QTest.qWait(20)
        assert visible_tabs(w) == ["Meridional"]
        assert w.central_views.currentWidget() is w.blade_plot
        assert not w.section_selector.isVisible()
        assert w.size() == size
        w.select_blade_row(kind)
        QTest.qWait(20)
        assert visible_tabs(w) == ["Blade Angle", "Thickness", "LE / TE", "Full Annulus"]
        assert w.central_views.currentWidget() is w.blade_plot
        assert w.size() == size
    after = w.get_parameters()
    assert after.hub == before.hub and after.shroud == before.shroud
    assert not any("Copy" in button.text() for button in w.section_selector.findChildren(QPushButton))


@pytest.mark.parametrize("tab,attribute", [("Blade Angle", "angle_editor"), ("Thickness", "thickness_editor")])
def test_right_edit_graph_and_numeric_tables_update_same_data(window, tab, attribute):
    w = window
    index = next(i for i in range(w.tabs.count()) if w.tabs.tabText(i) == tab)
    w.tabs.setCurrentIndex(index)
    w.tabs.tabBarClicked.emit(index)
    editor = getattr(w, attribute)
    assert w.central_views.currentWidget() is w.blade_plot
    assert w.vertical_splitter.widget(1).isAncestorOf(editor.plot)
    before = deepcopy(w.get_parameters())
    editor.move_point(1, .3, 45 if attribute == "angle_editor" else 5)
    w.update_geometry()
    assert w.get_parameters() != before
    assert editor.plot.isVisible()
    values = w.impeller_geometry.sections[0].beta_m_deg if attribute == "angle_editor" else w.impeller_geometry.sections[0].thickness
    np.testing.assert_array_equal(editor.series[0].curve.yData, values)
    w.undo()
    assert w.get_parameters() == before


def test_annulus_in_center_and_grouped_toolbar_preserves_settings(window):
    w = window
    index = next(i for i in range(w.tabs.count()) if w.tabs.tabText(i) == "Full Annulus")
    w.tabs.setCurrentIndex(index)
    w.annulus_2d.setChecked(True)
    assert w.central_views.currentWidget() is w.annulus_plot
    assert set(w.toolbar_groups) == {"Project", "Edit", "View", "Export"}
    view_actions = {action.text(): action for action in w.toolbar_groups["View"].menu().actions()}
    view_actions["Output Settings"].trigger()
    dialog = w._tool_dialogs["Output Settings"]
    assert dialog.isVisible() and w.output_page.isVisible()
    w.panel.controls["vane_count"].setValue(13)
    w.panel.controls["vane_count"].editingFinished.emit()
    assert w.get_parameters().geometry.vane_count == 13
    w.undo()
    assert w.get_parameters().geometry.vane_count == 20
    assert visible_tabs(w) == ["Blade Angle", "Thickness", "LE / TE", "Full Annulus"]
