import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import csv
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtCore import QPointF, Qt, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import BladeParameters, EdgeType, SurfaceMapping
from blade_designer.fileio.project_io import save_project, load_project


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def window(app):
    w = MainWindow()
    w.show()
    QTest.qWait(30)
    yield w
    w.timer.stop()
    w.close()
    w.deleteLater()
    app.processEvents()


def test_default_tabs_and_updates(window):
    assert window.geometry is not None
    assert [window.tabs.tabText(i) for i in range(window.tabs.count()) if window.tabs.isTabVisible(i)] == ["Blade Angle","Thickness","LE / TE","Splitter","Full Annulus"]
    assert not window.context_tabs.isVisible()
    assert window.central_views.currentWidget() is window.blade_plot
    assert window.blade_plot.getViewBox().state["aspectLocked"] == 1
    window.panel.controls["r_te"].setValue(170)
    QTest.qWait(400)
    assert window.geometry.camber.r[-1] == 170
    old = window.impeller_geometry.sections[0].camber.y.copy()
    old_diffuser = window.geometry.camber.y.copy()
    window.angle_editor.table.cellWidget(2,1).setValue(45)
    QTest.qWait(400)
    assert not np.allclose(window.impeller_geometry.sections[0].camber.y,old)
    np.testing.assert_array_equal(window.geometry.camber.y,old_diffuser)
    window.thickness_editor.table.cellWidget(1,1).setValue(6)
    window.panel.controls["vane_count"].setValue(12)
    QTest.qWait(400)
    assert window.impeller_geometry.sections[0].thickness.max() == pytest.approx(6)
    assert window.geometry.thickness.max() == pytest.approx(4)
    assert window.annulus_plot.vane_count == 12


@pytest.mark.parametrize("editor_name",["angle_editor","thickness_editor"])
def test_add_delete_and_endpoint_constraints(window,editor_name):
    e = getattr(window,editor_name)
    n = len(e.get_points())
    e.add_button.click()
    assert len(e.get_points()) == n+1
    e.delete_button.click()
    assert len(e.get_points()) == n
    e.table.selectRow(0)
    assert not e.delete_button.isEnabled()
    e.delete_point()
    assert len(e.get_points()) == n
    e.move_point(0,.4,2)
    assert e.get_points()[0].m_norm == 0
    e.move_point(n-1,.4,2)
    assert e.get_points()[-1].m_norm == 1
    e.move_point(1,2,3)
    assert e.get_points()[1].m_norm < e.get_points()[2].m_norm


@pytest.mark.parametrize("editor_name,tab", [("angle_editor",0),("thickness_editor",1)])
def test_real_graph_drag_events(window,app,editor_name,tab):
    window.tabs.setCurrentIndex(tab)
    QTest.qWait(100)
    e = getattr(window,editor_name)
    p = e.get_points()[1]
    viewport = e.plot.viewport()
    def screen(m,v):
        return e.plot.mapFromScene(e.plot.getViewBox().mapViewToScene(QPointF(m,v)))
    start = screen(p.m_norm,p.value)
    # Right-side graph is narrower; exceed Qt's pixel drag threshold.
    finish = screen(p.m_norm+.15,p.value+1.)
    QTest.mouseMove(viewport,start)
    QTest.qWait(30)
    QTest.mousePress(viewport,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
    for step in range(1,6):
        pos = start + (finish-start)*step/5
        local = QPointF(pos)
        event = QMouseEvent(QEvent.Type.MouseMove,local,QPointF(viewport.mapToGlobal(pos)),
                            Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        app.sendEvent(viewport,event)
        app.processEvents()
        QTest.qWait(20)  # Respect pyqtgraph mouse-move rate limiting.
    QTest.mouseRelease(viewport,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,finish)
    QTest.qWait(400)
    after = e.get_points()[1]
    assert after.m_norm != p.m_norm
    assert after.value != p.value
    assert "ERROR" not in window.statusBar().currentMessage()


def test_edge_types_mapping_curvature_metrics(window):
    for side in ("le","te"):
        for kind in EdgeType:
            combo = window.panel.controls[side+"_type"]
            combo.setCurrentIndex(combo.findData(kind))
            window.update_geometry()
            assert window.geometry is not None
            assert "ERROR" not in window.statusBar().currentMessage()
    window.panel.mapping.setCurrentIndex(window.panel.mapping.findData(SurfaceMapping.POSITIVE_IS_PS))
    window.update_geometry()
    assert window.geometry.resolved_mapping == SurfaceMapping.POSITIVE_IS_PS
    window.curvature_plot.absolute_check.setChecked(True)
    assert np.nanmin(window.curvature_plot.ps_curve.yData) >= 0
    window.curvature_plot.radius_check.setChecked(True)
    np.testing.assert_allclose(window.curvature_plot.ps_curve.yData,1/np.abs(window.geometry.curvature.ps_curvature))
    window.curvature_plot.ps_check.setChecked(False)
    assert not window.curvature_plot.ps_curve.isVisible()
    window.metrics_widget.choice.setCurrentIndex(1)
    assert len(window.metrics_widget.curve.yData) == 2001


def test_output_counts_and_file_actions(window,tmp_path,monkeypatch):
    window.panel.controls["ps_points"].setValue(51)
    window.panel.controls["ss_points"].setValue(77)
    window.panel.export_settings.digits.setValue(8)
    window.save_to_path(tmp_path/"saved.json")
    window.new_project()
    window.load_from_path(tmp_path/"saved.json")
    assert len(window.geometry.surfaces.ps.x) == 51
    assert len(window.geometry.surfaces.ss.x) == 77
    assert window.get_parameters().export.significant_digits == 8
    monkeypatch.setattr(QFileDialog,"getSaveFileName",lambda *args: (str(tmp_path/"segments.csv"),""))
    window.export_segments_dialog()
    with (tmp_path/"segments.csv").open() as f: rows = list(csv.DictReader(f))
    assert len(rows) == 21+51+21+77
    monkeypatch.setattr(QFileDialog,"getSaveFileName",lambda *args: (str(tmp_path/"contour.csv"),""))
    window.export_contour_dialog()
    with (tmp_path/"contour.csv").open() as f: rows = list(csv.DictReader(f))
    assert len(rows) == 21+51+21+77-4


def test_invalid_input_keeps_valid_geometry(window,tmp_path):
    previous = window.geometry
    window.panel.controls["r_te"].setValue(90)
    window.update_geometry()
    assert window.geometry is previous
    assert "ERROR" in window.statusBar().currentMessage()
    with pytest.raises(ValueError): window.export_to_path(tmp_path/"invalid.csv")
    assert not (tmp_path/"invalid.csv").exists()
    with pytest.raises(ValueError): window.save_to_path(tmp_path/"invalid.json")
    window.new_project()
    assert "ERROR" not in window.statusBar().currentMessage()


def test_precision_roundtrip_and_invalid_load(window,tmp_path):
    p = BladeParameters()
    p.geometry.r_le = 100.12345678901234
    p.blade_angle.points[1].m_norm = .2512345678901234
    p.thickness.points[1].value = 4.12345678901234
    save_project(tmp_path/"precise.json",p)
    window.load_from_path(tmp_path/"precise.json")
    assert window.get_parameters() == p
    (tmp_path/"bad.json").write_text('{"schema_version":"9"}')
    with pytest.raises(ValueError): window.load_from_path(tmp_path/"bad.json")
    assert window.get_parameters() == p


def test_view_preserved_on_geometry_change(window):
    view = window.blade_plot.getViewBox()
    view.setRange(xRange=(105,115),yRange=(5,15),padding=0)
    before = np.array(view.viewRange())
    window.panel.controls["r_te"].setValue(170)
    window.update_geometry()
    np.testing.assert_allclose(view.viewRange(),before)
    window.fit_view()
    assert not np.allclose(view.viewRange(),before)


@pytest.mark.parametrize('change',['angle','thickness','edge','meridional'])
def test_impeller_view_stays_fixed_for_each_editor(window,change):
 view=window.blade_plot.getViewBox()
 view.setRange(xRange=(-20,0),yRange=(30,50),padding=0)
 before=np.array(view.viewRange())
 if change=='angle':window.angle_editor.table.cellWidget(1,1).setValue(45)
 if change=='thickness':window.thickness_editor.table.cellWidget(1,1).setValue(5)
 if change=='edge':window.panel.controls['le_type'].setCurrentIndex(1)
 if change=='meridional':window.meridional_editor.table.cellWidget(2,1).setValue(65)
 window.update_geometry()
 assert 'ERROR' not in window.statusBar().currentMessage()
 np.testing.assert_allclose(view.viewRange(),before)
 assert window.impeller_geometry is not None
