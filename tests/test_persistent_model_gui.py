import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow
from blade_designer.geometry.annulus import rotate_xy


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_central_shape_remains_when_right_editors_change(window):
    w=window
    for name in ("Blade Angle","Thickness","LE / TE","Full Annulus"):
        w.tabs.setCurrentIndex(next(i for i in range(w.tabs.count()) if w.tabs.tabText(i)==name))
        assert w.central_views.currentWidget() is w.blade_plot
    w.navigator.tree.setCurrentItem(w.navigator.meridional_item)
    assert w.central_views.currentWidget() is w.blade_plot
    assert w.vertical_splitter.widget(1).isAncestorOf(w.meridional_editor.context)


def test_right_graph_click_selects_point_without_edit(window):
    w=window;e=w.angle_editor
    QTest.qWait(100)
    before=deepcopy(w.get_parameters());count=w.undo_stack.count()
    point=e.get_points()[1]
    position=e.plot.mapFromScene(e.plot.getViewBox().mapViewToScene(QPointF(point.m_norm,point.value)))
    e.table.clearSelection()
    QTest.mouseMove(e.plot.viewport(),position);QTest.qWait(30)
    QTest.mouseClick(e.plot.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,position)
    assert e.table.currentRow()==1
    assert w.get_parameters()==before and w.undo_stack.count()==count


@pytest.mark.parametrize("identifier",["row-1","row-2"])
def test_full_annulus_2d_3d_are_independent_and_keep_geometry_and_camera(window,identifier):
    w=window;w.select_blade_row(identifier)
    w.panel.controls["vane_count"].setValue(4);w.commit_edit();w.update_geometry()
    before=deepcopy(w.get_parameters());camera=deepcopy(w.model_preview_3d.camera_position)
    base=w.model_preview_3d.base_lines
    w.annulus_2d.setChecked(True)
    assert w.central_views.currentWidget() is w.annulus_plot
    assert not w.model_preview_3d.full_annulus
    w.annulus_3d.setChecked(True)
    assert w.model_preview_3d.full_annulus
    assert len(w.model_preview_3d.lines)==4*len(base)
    name="Hub camber" if identifier=="row-1" else "Diffuser camber"
    original=base[name][0]
    sampled=original[np.linspace(0,len(original)-1,min(len(original),151),dtype=int)]
    actual=w.model_preview_3d.lines[name+" • blade 2"][0]
    x,y=rotate_xy(sampled[:,0],sampled[:,1],np.pi/2)
    np.testing.assert_allclose(actual,np.column_stack((x,y,sampled[:,2])),atol=1e-12)
    for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)
    assert w.get_parameters()==before
    w.annulus_2d.setChecked(False)
    assert w.central_views.currentWidget() is w.blade_plot and w.model_preview_3d.full_annulus
    w.panel.controls["vane_count"].setValue(5);w.update_geometry()
    assert w.model_preview_3d.blade_count==5
    assert len(w.model_preview_3d.lines)==5*len(w.model_preview_3d.base_lines)
    w.annulus_3d.setChecked(False)
    assert len(w.model_preview_3d.lines)==len(w.model_preview_3d.base_lines)
