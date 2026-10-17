"""Show/tab fitting includes finite lines; data edits do not reset manual zoom."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication,QTabWidget,QWidget
from PySide6.QtCore import Qt,QPointF
from blade_designer.gui.plot_widgets import BladePlotWidget,CurvaturePlotWidget
from blade_designer.gui.profile_distribution_editor import ProfileDistributionEditor
from blade_designer.gui.control_point_editor import ControlPointEditor
from blade_designer.gui.context_meridional import ContextMeridional
from blade_designer.gui.flow_area_widget import FlowAreaWidget
from blade_designer.gui.metrics_widget import MetricsWidget
from blade_designer.gui.passage_widget import PassageWidget
from blade_designer.gui.optimization_widget import OptimizationWidget
from blade_designer.gui.main_window import MainWindow
from blade_designer.gui.preview_3d import Preview3D
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.models.parameters import BladeParameters


def settle(app):
    for _ in range(3):app.processEvents()


def assert_fits(plot):
    bounds=plot.viewRange();found=False
    for curve in plot.listDataItems():
        if not curve.isVisible():continue
        x,y=curve.getData()
        if x is None or y is None:continue
        x,y=np.asarray(x),np.asarray(y);finite=np.isfinite(x)&np.isfinite(y)
        if not finite.any():continue
        found=True
        for values,(lo,hi) in zip((x[finite],y[finite]),bounds):
            assert values.min()>=lo-1e-7 and values.max()<=hi+1e-7,(values.min(),values.max(),lo,hi)
    assert found


def test_drag_outside_control_points_ignores_empty_hit_array():
    app=QApplication.instance() or QApplication([]);editor=ControlPointEditor('blade_angle')
    class Drag:
        ignored=False
        def button(self):return Qt.MouseButton.LeftButton
        def isStart(self):return True
        def buttonDownPos(self):return QPointF(1000,1000)
        def ignore(self):self.ignored=True
    try:
        event=Drag();editor.handles.mouseDragEvent(event)
        assert event.ignored and editor.handles.drag_index is None
        editor.handles._clicked(None,np.array([],dtype=object),None)
        assert editor.table.currentRow()==-1
    finally:editor.close();editor.deleteLater();settle(app)


@pytest.mark.parametrize('factory',[
    BladePlotWidget,CurvaturePlotWidget,ContextMeridional,FlowAreaWidget,MetricsWidget,
    PassageWidget,OptimizationWidget,lambda:ProfileDistributionEditor('blade_angle'),
    lambda:ControlPointEditor('thickness')])
def test_graph_first_show_and_reopen_fit_finite_lines_without_edit_zoom_reset(factory):
    app=QApplication.instance() or QApplication([]);widget=factory()
    plot=widget if isinstance(widget,BladePlotWidget) else widget.plot
    curve=plot.plot([10,15,np.nan,20],[1000,-500,np.nan,700])
    tabs=QTabWidget();tabs.addTab(widget,'Graph');tabs.addTab(QWidget(),'Other');tabs.resize(900,700)
    try:
        plot.setRange(xRange=(-10,-5),yRange=(0,1),padding=0)
        tabs.show();settle(app);assert_fits(plot)
        plot.setRange(xRange=(100,101),yRange=(0,1),padding=0);manual=np.array(plot.viewRange())
        curve.setData([10,20],[1100,800]);settle(app)
        np.testing.assert_allclose(plot.viewRange(),manual)
        tabs.setCurrentIndex(1);settle(app);tabs.setCurrentIndex(0);settle(app);assert_fits(plot)
    finally:tabs.close();tabs.deleteLater();settle(app)


def test_real_tabs_analysis_modes_and_row_selection_frame_current_data():
    app=QApplication.instance() or QApplication([]);w=MainWindow();w.show();settle(app)
    try:
        for editor in (w.angle_editor,w.thickness_editor):
            w.tabs.setCurrentWidget(editor);settle(app);assert_fits(editor.plot)
            editor.plot.setRange(xRange=(2,3),yRange=(-200,-100),padding=0)
            w.tabs.setCurrentWidget(w.angle_editor if editor is w.thickness_editor else w.thickness_editor)
            settle(app);w.tabs.setCurrentWidget(editor);settle(app);assert_fits(editor.plot)
        w._select_meridional();settle(app);assert_fits(w.meridional_editor.plot)
        for name,widget in (('Flow Area',w.flow_area_widget),('Metrics',w.metrics_widget),('Diffuser Curvature',w.curvature_plot)):
            widget.plot.setRange(xRange=(20,21),yRange=(-20,-10),padding=0)
            dialog=w.show_analysis_view(name);settle(app);assert_fits(widget.plot)
            if name=='Metrics':widget.choice.setCurrentIndex(1);settle(app);assert_fits(widget.plot)
            if name=='Diffuser Curvature':widget.radius_check.setChecked(True);settle(app);assert_fits(widget.plot)
            dialog.close();settle(app)
        w.select_blade_row('row-2');settle(app);assert_fits(w.blade_plot)
        w.annulus_2d.setChecked(True);settle(app);assert_fits(w.annulus_plot)
    finally:
        for dialog in w._tool_dialogs.values():dialog.close()
        w.timer.stop();w.close();w.deleteLater();settle(app)


def test_3d_first_show_fits_without_resetting_orientation():
    app=QApplication.instance() or QApplication([]);view=Preview3D();view.resize(650,450)
    try:
        view.update_geometry(generate_impeller(BladeParameters()))
        view.camera_position.update(azimuth=72.,elevation=31.,scale=.01,center=np.array([1000.,1000.,1000.]))
        view.show();settle(app)
        assert view.camera_position['azimuth']==72 and view.camera_position['elevation']==31
        camera=view.camera_position;right,up,_=view._view_basis()
        xyz=np.concatenate([p for p,_ in view.lines.values()]+[faces.reshape(-1,3) for faces,_ in view.surfaces.values()])
        factor=min(view.width(),view.height())/(2*camera['scale'])
        x=((xyz-camera['center'])@right+camera['pan'][0])*factor+view.width()/2
        y=-((xyz-camera['center'])@up+camera['pan'][1])*factor+(view.height()+view._plot_top-25)/2
        assert x.min()>=0 and x.max()<=view.width()
        assert y.min()>=view._plot_top and y.max()<=view.height()-25
    finally:view.close();view.deleteLater();settle(app)
