import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = MainWindow();w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_2d_above_3d_stays_visible_and_tracks_selected_target(window):
    w = window
    size = w.size()
    assert w.model_splitter.widget(0) is w.central_views
    assert w.model_splitter.widget(1) is w.model_preview_3d
    assert w.central_views.isVisible() and w.model_preview_3d.isVisible()
    assert w.central_views.mapTo(w,w.central_views.rect().center()).y() < w.model_preview_3d.mapTo(w,w.model_preview_3d.rect().center()).y()
    w.model_preview_3d.camera_position["azimuth"] = 72
    for identifier in ("row-2","row-1"):
        w.select_blade_row(identifier)
        assert w.model_preview_3d.isVisible() and w.size() == size
        assert w.model_preview_3d.camera_position["azimuth"] == 72
        if identifier == "row-2":
            points = w.model_preview_3d.lines["Diffuser camber"][0]
            np.testing.assert_array_equal(points[:,:2], np.column_stack((w.geometry.camber.x,w.geometry.camber.y)))
            assert np.all(points[:,2] == 0)
        else:
            np.testing.assert_array_equal(w.model_preview_3d.lines["Hub camber"][0],w.impeller_geometry.sections[0].camber.xyz)
        view = w.model_preview_3d
        view.fit_view()
        xyz = np.concatenate([data[0] for data in view.lines.values()])
        camera = view.camera_position
        a,e = np.deg2rad([camera["azimuth"],camera["elevation"]])
        right = np.array([-np.sin(a),np.cos(a),0])
        up = np.array([-np.cos(a)*np.sin(e),-np.sin(a)*np.sin(e),np.cos(e)])
        factor = min(view.width(),view.height())/(2*camera["scale"])
        x = ((xyz-camera["center"])@right+camera["pan"][0])*factor+view.width()/2
        y = -((xyz-camera["center"])@up+camera["pan"][1])*factor+(view.height()+60)/2
        assert x.min() >= 0 and x.max() <= view.width()
        assert y.min() >= 60 and y.max() <= view.height()-25


def test_assignment_undo_segment_reorder_and_row_delete_restore(window, tmp_path):
    w = window;w.navigator.tree.setCurrentItem(w.navigator.meridional_item)
    before = deepcopy(w.get_parameters())
    assert w.meridional_editor.table.horizontalHeader().visualIndex(5) == 1
    box = w.meridional_editor.table.cellWidget(1,5)
    box.setCurrentIndex(box.findData("row-1"))
    owned = deepcopy(w.get_parameters())
    assert owned.hub.segments[1].blade_row == "row-1"
    assert len(w.meridional_editor.ownership_items) == 2
    w.undo();assert w.get_parameters() == before
    w.redo();assert w.get_parameters() == owned
    w.meridional_editor.table.selectRow(1)
    w.meridional_editor.move_segment(1)
    assert w.get_parameters().hub.segments[2].blade_row == "row-1"
    w.undo();assert w.get_parameters() == owned
    path = tmp_path / "rows.json";w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters().hub.segments[1].blade_row == "row-1"
    w.select_blade_row("row-1")
    w.delete_blade_row()
    assert all(s.blade_row is None for s in w.get_parameters().hub.segments)
    w.undo();assert w.get_parameters().hub.segments[1].blade_row == "row-1"
