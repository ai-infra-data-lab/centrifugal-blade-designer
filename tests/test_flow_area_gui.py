import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import numpy as np
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow

def test_area_cursor_links_and_view_preservation():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    assert not w.flow_area_result.errors
    w.flow_area_widget.select_position(.5)
    p=min(w.flow_area_result.stations,key=lambda s:abs(s.m_flow_norm-.5))
    np.testing.assert_allclose(w.context_meridional.cursor.xData,[p.hub_z,p.shroud_z])
    np.testing.assert_allclose(w.meridional_editor.context.cursor.yData,[p.hub_r,p.shroud_r])
    assert "Hub R" in w.flow_area_widget.info.text() and "m =" in w.flow_area_widget.info.text()
    w.context_meridional.stationSelected.emit(.85)
    assert w.flow_area_widget.cursor.xData[0]==.85
    plots=[w.context_meridional.plot,w.flow_area_widget.plot,w.meridional_editor.plot]
    for plot in plots:plot.setRange(xRange=(.2,.8),yRange=(20,40),padding=0)
    before=[np.array(plot.viewRange()) for plot in plots]
    w.meridional_editor.station_table.cellWidget(1,1).setValue(.2)
    w.update_geometry()
    assert w.get_parameters().blade_le_fraction==.2
    assert w.output_editor.controls["blade_le_fraction"].value()==.2
    for plot,ranges in zip(plots,before):np.testing.assert_allclose(plot.viewRange(),ranges)
    assert w.flow_area_widget.table.item(1,2).text()=="1"
    assert w.blade_plot.isVisible()
    previous=w.impeller_geometry
    w.meridional_editor.station_table.cellWidget(3,1).setValue(.8)
    w.update_geometry()
    assert w.impeller_geometry is previous
    assert "ERROR" in w.statusBar().currentMessage()
    w.timer.stop();w.close()

def test_uncovered_wall_ends_show_missing_area_without_crash():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    view=w.blade_plot.getViewBox()
    view.setRange(xRange=(110,130),yRange=(0,20),padding=0)
    before=np.array(view.viewRange())
    w.meridional_editor.curves[1].segments[-1].length=70
    w.update_geometry()
    app.processEvents()
    np.testing.assert_allclose(view.viewRange(),before)
    assert w.flow_area_result.errors
    assert w.flow_area_widget.table.item(5,1).text()=="N/A"
    w.flow_area_widget.select_position(1,exact=True)
    assert "unavailable" in w.flow_area_widget.info.text()
    assert w.flow_area_widget.cursor.xData is None
    assert "FLOW AREA" in w.messages.toPlainText()
    w.timer.stop();w.close()
