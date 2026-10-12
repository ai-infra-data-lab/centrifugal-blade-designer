import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    QTest.qWait(40)
    yield window
    window.timer.stop()
    window.close()
    window.deleteLater()
    app.processEvents()


def choose(window, identifier):
    tree = window.navigator.tree
    for index in range(window.navigator.rows_item.childCount()):
        item = window.navigator.rows_item.child(index)
        if item.data(0, Qt.ItemDataRole.UserRole) == identifier:
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton,
                            pos=tree.visualItemRect(item).center())
            return
    raise AssertionError(identifier)


def test_vertical_navigation_and_independent_row_edits(window):
    w = window
    tree = w.navigator.tree
    QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton,
                    pos=tree.visualItemRect(w.navigator.meridional_item).center())
    assert w.tabs.tabText(w.tabs.currentIndex()) == "Meridional"
    choose(w, "row-1")
    w.panel.controls["vane_count"].setValue(11)
    w.angle_editor.table.cellWidget(1, 1).setValue(44)
    w.commit_edit()
    choose(w, "row-2")
    assert w.view_mode.currentIndex() == 1
    assert w.panel.controls["vane_count"].value() == 20
    w.panel.controls["vane_count"].setValue(15)
    w.thickness_editor.table.cellWidget(1, 1).setValue(6)
    w.meridional_editor.blade_edges.controls["diffuser_edges", "leading_edge", "hub"].setValue(.91)
    w.commit_edit()
    choose(w, "row-1")
    assert w.panel.controls["vane_count"].value() == 11
    assert w.angle_editor.get_points()[1].value == 44
    choose(w, "row-2")
    assert w.panel.controls["vane_count"].value() == 15
    assert w.thickness_editor.get_points()[1].value == 6
    assert w.get_parameters().diffuser_edges.leading_edge.hub_m_flow_norm == .91


def add_via_dialog(window, kind, name):
    window.navigator.add_button.click()
    dialog = window.navigator.add_dialog
    assert dialog.isVisible() and dialog.isModal()
    dialog.name_edit.setText(name)
    dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData(kind))
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()


@pytest.mark.parametrize("kind", ["impeller", "diffuser"])
def test_rename_updates_row_labels_preserves_data_and_undo_save(window,tmp_path,kind):
    w=window
    w.add_blade_row(kind,"元の翼列")
    identifier=w.get_parameters().active_blade_row
    # Ownership uses stable IDs even when a visible name changes.
    w.meridional_editor.curves[0].segments[0].blade_row=identifier
    w.commit_edit()
    before=deepcopy(w.get_parameters());history=w.undo_stack.count()
    w.navigator.rename_button.click();dialog=w.navigator.rename_dialog
    assert dialog.isVisible() and dialog.isModal()
    assert dialog.name_edit.text()=="元の翼列"
    dialog.name_edit.setText("  改名した翼列  ")
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    after=deepcopy(w.get_parameters())
    expected=deepcopy(before);expected.blade_rows[-1].name="改名した翼列"
    assert after==expected
    assert w.undo_stack.count()==history+1
    assert w.navigator.tree.currentItem().text(0)=="改名した翼列"
    assert "改名した翼列" in w.editor_target_label.text()
    assert "改名した翼列" in w.model_preview_3d.model_label
    table=w.meridional_editor.blade_edges.table
    offset=4*next(i for i,row in enumerate(after.blade_rows) if row.identifier==identifier)
    assert [table.item(i,0).text() for i in range(offset,offset+4)]==["改名した翼列"]*4
    assert (identifier,"改名した翼列") in w.meridional_editor.blade_rows
    w.undo();assert w.get_parameters()==before
    assert table.item(offset,0).text()=="元の翼列"
    w.redo();assert w.get_parameters()==after
    path=tmp_path/"renamed.json";w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters()==after
    w.navigator.tree.setCurrentItem(w.navigator.meridional_item)
    assert table.item(offset,0).text()=="改名した翼列"
    assert not w.navigator.rename_button.isEnabled()


def test_rename_blank_cancel_and_same_name_do_not_change_project(window):
    w=window;choose(w,"row-1")
    before=deepcopy(w.get_parameters());history=w.undo_stack.count()
    w.navigator.rename_button.click();dialog=w.navigator.rename_dialog
    ok=dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    dialog.name_edit.setText("   ");assert not ok.isEnabled()
    dialog.name_edit.setText("取消す名前");assert ok.isEnabled()
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert w.get_parameters()==before and w.undo_stack.count()==history
    w.rename_blade_row("row-1","  Impeller  ")
    assert w.get_parameters()==before and w.undo_stack.count()==history
    with pytest.raises(ValueError,match="name is required"):
        w.rename_blade_row("row-1"," ")
    assert w.get_parameters()==before


def test_row_names_match_navigation_for_legacy_and_selected_duplicate_kind(window):
    w=window;table=w.meridional_editor.blade_edges.table
    assert table.item(0,0).text()==w.navigator.rows_item.child(0).text(0)=="Impeller"
    assert table.item(4,0).text()==w.navigator.rows_item.child(1).text(0)=="Diffuser"
    assert w.get_parameters().blade_rows is None
    w.add_blade_row("impeller","第2インペラ")
    assert table.rowCount()==12 and table.item(8,0).text()=="第2インペラ"
    choose(w,"row-1");assert table.item(0,0).text()=="Impeller"
    choose(w,"row-3");assert table.item(8,0).text()=="第2インペラ"
    assert table.item(0,0).text()=="Impeller" and table.item(4,0).text()=="Diffuser"


def test_add_dialog_cancel_and_blank_name_leave_project_unchanged(window):
    w = window
    before = deepcopy(w.get_parameters())
    history = w.undo_stack.count()
    w.navigator.add_button.click()
    dialog = w.navigator.add_dialog
    assert dialog.isVisible()
    assert w.get_parameters() == before
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()
    dialog.name_edit.setText("   ")
    assert not ok.isEnabled()
    dialog.name_edit.setText("キャンセルする翼列")
    assert ok.isEnabled()
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert w.get_parameters() == before
    assert w.undo_stack.count() == history


@pytest.mark.parametrize("kind", ["impeller", "diffuser"])
def test_add_move_delete_undo_save_load(window, tmp_path, kind):
    w = window
    before = deepcopy(w.get_parameters())
    add_via_dialog(w, kind, "  独立翼列  ")
    added = deepcopy(w.get_parameters())
    identifier = added.active_blade_row
    assert len(added.blade_rows) == 3
    assert added.blade_rows[-1].kind == kind
    assert added.blade_rows[-1].name == "独立翼列"
    w.undo()
    assert w.get_parameters() == before
    w.redo()
    assert w.get_parameters() == added
    w.angle_editor.table.cellWidget(1, 1).setValue(36)
    w.panel.controls["vane_count"].setValue(12)
    w.commit_edit()
    before_move = deepcopy(w.get_parameters())
    original = before_move.blade_rows[0].parameters
    assert original.geometry.vane_count == before.geometry.vane_count
    assert original.sections[0].blade_angle == before.sections[0].blade_angle
    assert original.diffuser_profile == before.diffuser_profile
    view = w.blade_plot.getViewBox()
    view.setRange(xRange=(10, 40), yRange=(20, 50), padding=0)
    ranges = np.array(view.viewRange())
    camera = deepcopy(w.preview_3d.camera_position)
    w.navigator.up_button.click()
    moved = deepcopy(w.get_parameters())
    assert moved.blade_rows[1].identifier == identifier
    assert {r.identifier: r.parameters for r in moved.blade_rows} == {r.identifier: r.parameters for r in before_move.blade_rows}
    w.undo()
    assert w.get_parameters() == before_move
    w.redo()
    assert w.get_parameters() == moved
    assert w.get_parameters().blade_rows[1].name == "独立翼列"
    w.navigator.delete_button.click()
    assert len(w.get_parameters().blade_rows) == 2
    w.undo()
    assert w.get_parameters() == moved
    np.testing.assert_allclose(view.viewRange(), ranges)
    for key in camera:
        np.testing.assert_array_equal(w.preview_3d.camera_position[key], camera[key])
    path = tmp_path / "multiple.json"
    w.save_to_path(path)
    w.new_project()
    w.load_from_path(path)
    assert w.get_parameters() == moved
    assert w.navigator.rows_item.childCount() == 3
    choose(w, identifier)
    assert w.angle_editor.get_points()[1].value == 36
    assert w.panel.controls["vane_count"].value() == 12


def test_last_row_protected_and_shared_wall_edit(window):
    w = window
    w.add_blade_row("impeller")
    w.delete_blade_row()
    w.delete_blade_row()
    assert len(w.get_parameters().blade_rows) == 1
    before = deepcopy(w.get_parameters())
    assert not w.navigator.delete_button.isEnabled()
    w.delete_blade_row()
    assert w.get_parameters() == before
    w.add_blade_row("diffuser")
    w.meridional_editor.table.cellWidget(2,1).setValue(65)
    w.commit_edit()
    shared = deepcopy(w.get_parameters().hub)
    choose(w, "row-1")
    assert w.get_parameters().hub == shared


def test_current_row_click_and_add_from_meridional(window):
    w = window
    choose(w, "row-1")
    assert w.get_parameters().blade_rows is not None
    w.navigator.tree.setCurrentItem(w.navigator.meridional_item)
    add_via_dialog(w, "impeller", "追加インペラ")
    assert w.navigator.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == w.get_parameters().active_blade_row
    assert w.navigator.delete_button.isEnabled()
    w.navigator.tree.setCurrentItem(w.navigator.meridional_item)
    w.navigator.tree.setCurrentItem(w.navigator.rows_item)
    assert w.tabs.currentWidget() is w.angle_editor
    assert w.navigator.tree.currentItem().parent() is w.navigator.rows_item


def test_selected_diffuser_csv_and_wrong_type_rejected(window, tmp_path):
    import csv
    w = window
    w.add_blade_row("diffuser")
    w.panel.controls["vane_count"].setValue(12)
    w.angle_editor.table.cellWidget(1, 1).setValue(36)
    w.update_geometry()
    path = tmp_path / "selected.csv"
    w.export_to_path(path)
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    choose(w, "row-1")
    with pytest.raises(ValueError, match="Select a Diffuser"):
        w.export_to_path(tmp_path / "wrong.csv")
    assert not (tmp_path / "wrong.csv").exists()


def test_row_optimization_is_separate_and_applies_to_selected_diffuser(window):
    w = window
    w.add_blade_row("diffuser")
    identifier = w.get_parameters().active_blade_row
    w.angle_editor.table.cellWidget(1, 1).setValue(36)
    w.commit_edit()
    before = deepcopy(w.get_parameters())
    optimizer = w.open_optimization_mode()
    try:
        assert optimizer.get_parameters().active_blade_row == identifier
        assert optimizer.tabs.tabText(optimizer.tabs.currentIndex()) == "Optimization"
        candidate = deepcopy(optimizer.optimization_widget.baseline)
        candidate.sections[0].blade_angle.points[1].value = 33
        optimizer.apply_optimization_candidate(candidate)
        after = optimizer.get_parameters()
        assert after.diffuser_profile.blade_angle.points[1].value == 33
        assert after.blade_rows[-1].parameters.diffuser_profile.blade_angle.points[1].value == 33
        assert after.blade_rows[:-1] == before.blade_rows[:-1]
        assert w.get_parameters() == before
        optimizer.undo()
        assert optimizer.get_parameters() == before
        optimizer.select_blade_row("row-1")
        impeller = deepcopy(optimizer.get_parameters())
        optimizer.apply_optimization_candidate(candidate)
        assert optimizer.get_parameters() == impeller
        assert "Select a Diffuser" in optimizer.optimization_widget.report.toPlainText()
    finally:
        optimizer.timer.stop()
        optimizer.close()
        optimizer.deleteLater()
