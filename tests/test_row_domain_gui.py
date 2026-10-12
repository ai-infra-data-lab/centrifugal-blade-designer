import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.meridional import LineSegmentParameters,ArcSegmentParameters
from blade_designer.geometry.meridional_segments import convert_segment_type,generate_meridional


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
            points = w.model_preview_3d.lines["Hub camber"][0]
            np.testing.assert_array_equal(points,w.diffuser_geometry.sections[0].camber.xyz)
            assert np.any(points[:,2] != 0) and w.model_preview_3d.spanwise_lines
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


@pytest.mark.parametrize("original_arc",[False,True])
@pytest.mark.parametrize("wall_index",[0,1])
def test_added_segment_type_change_owner_undo_and_json(window,tmp_path,original_arc,wall_index):
    w=window;editor=w.meridional_editor
    w.navigator.tree.setCurrentItem(w.navigator.meridional_item)
    editor.selector.setCurrentIndex(wall_index);editor.add_segment(original_arc)
    index=editor.table.rowCount()-1
    owner=editor.table.cellWidget(index,5)
    owner.setCurrentIndex(owner.findData("row-1"))
    before=deepcopy(w.get_parameters());history=w.undo_stack.count()
    wall=("hub","shroud")[wall_index]
    length=generate_meridional(getattr(before,wall)).length
    combo=editor.table.cellWidget(index,0)
    assert combo.currentText()==("Arc" if original_arc else "Line")
    combo.setCurrentIndex(int(not original_arc))
    after=deepcopy(w.get_parameters());segment=getattr(after,wall).segments[index]
    assert isinstance(segment,LineSegmentParameters if original_arc else ArcSegmentParameters)
    assert segment.blade_row=="row-1"
    assert getattr(after,wall).segments[:index]==getattr(before,wall).segments[:index]
    assert getattr(after,("hub","shroud")[1-wall_index])==getattr(before,("hub","shroud")[1-wall_index])
    assert after.impeller_edges==before.impeller_edges and after.diffuser_edges==before.diffuser_edges
    assert generate_meridional(getattr(after,wall)).length==pytest.approx(length,abs=1e-12)
    assert editor.table.currentRow()==index
    assert (editor.table.cellWidget(index,1) is not None)==original_arc
    assert (editor.table.cellWidget(index,2) is not None)==(not original_arc)
    assert (editor.table.cellWidget(index,3) is not None)==(not original_arc)
    assert (editor.table.cellWidget(index,4) is not None)==(not original_arc)
    assert w.undo_stack.count()==history+1
    w.undo();assert w.get_parameters()==before
    w.redo();assert w.get_parameters()==after
    path=tmp_path/"converted.json";w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters()==after
    editor.selector.setCurrentIndex(wall_index)
    editor.table.cellWidget(index,0).setCurrentIndex(int(original_arc))
    restored=getattr(w.get_parameters(),wall).segments[index]
    assert isinstance(restored,ArcSegmentParameters if original_arc else LineSegmentParameters)
    assert restored.blade_row=="row-1"


def test_conversion_analytic_length_and_owner():
    line=LineSegmentParameters(73.25,"row-7")
    arc=convert_segment_type(line,True)
    assert arc.radius*np.deg2rad(arc.sweep_deg)==pytest.approx(line.length,abs=1e-12)
    assert arc.sweep_deg==35 and not arc.clockwise and arc.blade_row==line.blade_row
    restored=convert_segment_type(arc,False)
    assert restored.length==pytest.approx(line.length,abs=1e-12)
    assert restored.blade_row==line.blade_row
    arc=ArcSegmentParameters(12,80,True,"row-2")
    assert convert_segment_type(arc,False).length==pytest.approx(12*np.deg2rad(80))


def test_conversion_rejects_nonpositive_or_nonfinite_length():
    for segment in (LineSegmentParameters(0),LineSegmentParameters(float("nan")),
                    ArcSegmentParameters(0,35),ArcSegmentParameters(-2,35)):
        with pytest.raises(ValueError,match="positive finite"):
            convert_segment_type(segment,not isinstance(segment,ArcSegmentParameters))
