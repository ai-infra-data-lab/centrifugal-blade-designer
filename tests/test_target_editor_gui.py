import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow

@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();QTest.qWait(40)
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()

def test_target_angle_thickness_and_section_isolation(window):
    w=window
    w.angle_editor.table.cellWidget(1,1).setValue(44)
    w.thickness_editor.table.cellWidget(1,1).setValue(5)
    w.update_geometry();hub=w.impeller_geometry.sections[0].master_ps.xyz.copy()
    w.section_selector.combo.setCurrentIndex(1)
    w.angle_editor.table.cellWidget(1,1).setValue(38)
    w.thickness_editor.table.cellWidget(1,1).setValue(6)
    w.update_geometry();tip=w.impeller_geometry.sections[1].master_ps.xyz.copy()
    w.view_mode.setCurrentIndex(1)
    assert w.editor_target_label.text()=="Editing: Diffuser"
    assert not w.section_selector.isVisible()
    assert w.angle_editor.get_points()[1].value==62
    assert w.thickness_editor.get_points()[1].value==4
    w.angle_editor.table.cellWidget(1,1).setValue(29)
    w.thickness_editor.table.cellWidget(1,1).setValue(7)
    w.update_geometry()
    assert w.geometry.thickness.max()==pytest.approx(7)
    np.testing.assert_array_equal(w.impeller_geometry.sections[0].master_ps.xyz,hub)
    np.testing.assert_array_equal(w.impeller_geometry.sections[1].master_ps.xyz,tip)
    np.testing.assert_array_equal(w.angle_editor.curve.yData,np.rad2deg(w.geometry.camber.beta_m_rad))
    w.view_mode.setCurrentIndex(0)
    assert w.section_selector.isVisible()
    assert w.angle_editor.get_points()[1].value==38
    assert w.thickness_editor.get_points()[1].value==6
    w.section_selector.combo.setCurrentIndex(0)
    assert w.angle_editor.get_points()[1].value==44
    assert w.thickness_editor.get_points()[1].value==5
    w.view_mode.setCurrentIndex(1)
    assert w.angle_editor.get_points()[1].value==29
    assert w.thickness_editor.get_points()[1].value==7

@pytest.mark.parametrize("plane",["XY","XZ","YZ"])
def test_projection_uses_true_section_coordinates(window,plane):
    w=window;w.projection.setCurrentText(plane)
    section=w.impeller_geometry.sections[0]
    x,y=w.blade_plot.camber_curve.getData()
    np.testing.assert_array_equal(x,getattr(section.camber,plane[0].lower()))
    np.testing.assert_array_equal(y,getattr(section.camber,plane[1].lower()))
    for name,item in w.blade_plot.curves.items():
        x,y=item.getData();curve=getattr(section,"master_"+name.lower())
        np.testing.assert_array_equal(x,getattr(curve,plane[0].lower()))
        np.testing.assert_array_equal(y,getattr(curve,plane[1].lower()))
    assert plane+" projection" in w.blade_plot.plotItem.titleLabel.text
    w.view_mode.setCurrentIndex(1)
    assert not w.projection.isEnabled() and w.projection.currentText()=="XY"
    np.testing.assert_array_equal(w.blade_plot.camber_curve.xData,w.geometry.camber.x)
    np.testing.assert_array_equal(w.blade_plot.camber_curve.yData,w.geometry.camber.y)
    w.view_mode.setCurrentIndex(0)
    assert w.projection.isEnabled() and w.projection.currentText()==plane

def test_target_switch_save_load_undo_and_preserved_view(window,tmp_path):
    w=window;view=w.blade_plot.getViewBox()
    view.setRange(xRange=(10,40),yRange=(20,50),padding=0)
    ranges=np.array(view.viewRange());camera=deepcopy(w.preview_3d.camera_position)
    w.angle_editor.table.cellWidget(1,1).setValue(46)
    w.angle_editor.table.cellWidget(1,1).editingFinished.emit()
    impeller=deepcopy(w.get_parameters())
    w.view_mode.setCurrentIndex(1)
    w.thickness_editor.table.cellWidget(1,1).setValue(8)
    w.thickness_editor.table.cellWidget(1,1).editingFinished.emit()
    both=deepcopy(w.get_parameters())
    w.projection.setCurrentText("YZ")
    w.undo();assert w.get_parameters()==impeller and w.view_mode.currentIndex()==1
    w.undo();assert w.view_mode.currentIndex()==0 and w.angle_editor.get_points()[1].value==62
    w.redo();w.redo();assert w.get_parameters()==both and w.view_mode.currentIndex()==1
    np.testing.assert_allclose(view.viewRange(),ranges)
    for key,value in camera.items():np.testing.assert_array_equal(w.preview_3d.camera_position[key],value)
    w.save_to_path(tmp_path/"targets.json");w.new_project();w.load_from_path(tmp_path/"targets.json")
    assert w.get_parameters()==both
    w.view_mode.setCurrentIndex(0);assert w.angle_editor.get_points()[1].value==46
    w.view_mode.setCurrentIndex(1);assert w.thickness_editor.get_points()[1].value==8

def test_diffuser_optimization_preserves_impeller_and_is_undoable(window):
    w=window
    w.angle_editor.table.cellWidget(1,1).setValue(44);w.commit_edit()
    before=deepcopy(w.get_parameters())
    design=w
    w=design.open_optimization_mode()
    w.capture_optimization_baseline()
    assert w.optimization_widget.baseline.blade_angle.points[1].value==62
    row=next(row for row in w.optimization_widget.rows if row["parameter"].name=="beta_te")
    row["initial"].setValue(-1)
    w.optimization_widget.preview_candidate()
    assert w.optimization_widget.last_result.feasible
    w.optimization_widget.apply_candidate()
    assert w.get_parameters().sections==before.sections
    assert w.get_parameters().diffuser_profile.blade_angle.points[-1].value==49
    assert w.view_mode.currentIndex()==1
    assert design.get_parameters()==before
    w.undo();assert w.get_parameters()==before
    w.timer.stop();w.close();w.deleteLater()
