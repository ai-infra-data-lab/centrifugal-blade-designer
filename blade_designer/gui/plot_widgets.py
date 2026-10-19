import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox
from ..models.geometry import BladeGeometry
from ..geometry.annulus import rotate_xy, project_annulus
from ..geometry.resample import closed_contour
from .plot_fitting import install_plot_fit

COLORS = {"LE":"#e5c76b", "PS":"#56d9e0", "TE":"#eead72", "SS":"#f6948c"}


def configure_plot(plot: pg.PlotWidget, xlabel: str, ylabel: str) -> None:
    install_plot_fit(plot)
    plot.setLabel("bottom",xlabel)
    plot.setLabel("left",ylabel)
    plot.getAxis("bottom").setHeight(48)
    # Stable viewport dimensions prevent tick label widths changing a locked view.
    plot.getAxis("left").setWidth(80)
    plot.showGrid(x=True,y=True,alpha=.15)
    for name in ("bottom","left"):
        plot.getAxis(name).setTextPen("#d1dae7")
        plot.getAxis(name).setPen("#8e9caf")


class SplitterPlotMixin:
    def update_splitter(self,section,projection,blade_count=1):
        if not hasattr(self,"splitter_curves"):self.splitter_curves={}
        if section is None:
            for curve in self.splitter_curves.values():curve.setData([],[])
            return
        for name in COLORS:
            if name not in self.splitter_curves:
                self.splitter_curves[name]=self.plot(
                    pen=pg.mkPen(COLORS[name],width=2,style=Qt.PenStyle.DashLine),name="Splitter "+name)
            segment=getattr(section,"master_"+name.lower())
            x,y=project_annulus(segment.x,segment.y,segment.z,blade_count,projection)
            self.splitter_curves[name].setData(x,y,connect="finite")


class BladePlotWidget(SplitterPlotMixin,pg.PlotWidget):
    def __init__(self) -> None:
        super().__init__(background="#101c2b")
        configure_plot(self,"X [mm]","Y [mm]")
        self.setAspectLocked(True)
        self.addLegend(labelTextColor="#d1dae7")
        self.camber_curve = self.plot(pen=pg.mkPen("#aab4c5",width=1),name="Camber")
        self.curves = {name:self.plot(pen=pg.mkPen(color,width=2),name=name) for name,color in COLORS.items()}
        self.adjacent = self.plot(pen=pg.mkPen("#697589",width=1),name="Adjacent blade")
        self.throat_line = self.plot(pen=pg.mkPen("#8deb87",width=3),symbol="o",symbolSize=5,name="Throat")

    def update_geometry(self, geometry: BladeGeometry, vane_count: int) -> None:
        self.camber_curve.setData(geometry.camber.x,geometry.camber.y)
        for name,curve in self.curves.items():
            segment = getattr(geometry.master_surfaces,name.lower())
            curve.setData(segment.x,segment.y)
        throat = geometry.metrics.throat
        if throat is None:
            self.adjacent.setData([],[])
            self.throat_line.setData([],[])
        else:
            xy,_ = closed_contour(geometry.master_surfaces,True)
            x,y = rotate_xy(xy[:,0],xy[:,1],2*np.pi/vane_count)
            self.adjacent.setData(x,y)
            self.throat_line.setData([throat.blade1_x,throat.blade2_x],[throat.blade1_y,throat.blade2_y])
        self.disableAutoRange()


class FullAnnulusPlotWidget(SplitterPlotMixin,pg.PlotWidget):
    def __init__(self) -> None:
        super().__init__(background="#101c2b")
        configure_plot(self,"X [mm]","Y [mm]")
        self.setAspectLocked(True)
        self.addLegend(labelTextColor="#d1dae7")
        self.curves = {name:self.plot(pen=color,name=name) for name,color in COLORS.items()}
        self.throat_line = self.plot(pen=pg.mkPen("#8deb87",width=3),name="Throat")
        self.vane_count = 0

    def update_annulus(self, geometry: BladeGeometry, vane_count: int) -> None:
        self.setTitle(f"Vaned Diffuser • XY • {vane_count} blades")
        self.setLabel("bottom", "X [mm]")
        self.setLabel("left", "Y [mm]")
        for name,curve in self.curves.items():
            segment = getattr(geometry.master_surfaces,name.lower())
            pairs = [rotate_xy(segment.x,segment.y,2*np.pi*k/vane_count) for k in range(vane_count)]
            curve.setData(np.concatenate([np.r_[x,np.nan] for x,y in pairs]),
                          np.concatenate([np.r_[y,np.nan] for x,y in pairs]),connect="finite")
        t = geometry.metrics.throat
        self.throat_line.setData([] if t is None else [t.blade1_x,t.blade2_x],
                                 [] if t is None else [t.blade1_y,t.blade2_y])
        self.vane_count = vane_count
        self.disableAutoRange()

    def update_impeller_annulus(self, section, blade_count: int, projection: str, row_name="Impeller") -> None:
        name = "Hub" if section.span == 0 else "Tip" if section.span == 1 else f"Span {section.span:.6g}"
        self.setTitle(f"{row_name} • {name} • {projection} • {blade_count} blades")
        self.setLabel("bottom", projection[0] + " [mm]")
        self.setLabel("left", projection[1] + " [mm]")
        for name, curve in self.curves.items():
            segment = getattr(section, "master_" + name.lower())
            horizontal, vertical = project_annulus(segment.x, segment.y, segment.z, blade_count, projection)
            curve.setData(horizontal, vertical, connect="finite")
        self.throat_line.setData([], [])
        self.vane_count = blade_count
        self.disableAutoRange()


class CurvaturePlotWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        options = QHBoxLayout()
        self.ps_check = QCheckBox("PS")
        self.ss_check = QCheckBox("SS")
        self.absolute_check = QCheckBox("Absolute Curvature")
        self.radius_check = QCheckBox("Radius of Curvature")
        self.ps_check.setChecked(True)
        self.ss_check.setChecked(True)
        for box in (self.ps_check,self.ss_check,self.absolute_check,self.radius_check):
            options.addWidget(box)
            box.toggled.connect(self._refresh)
        options.addStretch()
        layout.addLayout(options)
        self.plot = pg.PlotWidget(background="#101c2b")
        configure_plot(self.plot,"Normalized Meridional","Curvature [1/mm]")
        self.plot.addLegend(labelTextColor="#d1dae7")
        self.ps_curve = self.plot.plot(pen=pg.mkPen(COLORS["PS"],width=2),name="PS")
        self.ss_curve = self.plot.plot(pen=pg.mkPen(COLORS["SS"],width=2),name="SS")
        layout.addWidget(self.plot)
        self.geometry: BladeGeometry | None = None

    def update_geometry(self, geometry: BladeGeometry) -> None:
        self.geometry = geometry
        self._refresh()

    def _refresh(self) -> None:
        if self.geometry is None:
            return
        c = self.geometry.curvature
        radius = self.radius_check.isChecked()
        self.absolute_check.setEnabled(not radius)
        self.plot.setLabel("left","Radius of Curvature [mm]" if radius else "Curvature [1/mm]")
        for k,curve,check in ((c.ps_curvature,self.ps_curve,self.ps_check),(c.ss_curvature,self.ss_curve,self.ss_check)):
            values = k.copy()
            if radius:
                values = np.divide(1.,np.abs(k),out=np.full_like(k,np.nan),where=np.abs(k)>1e-12)
            elif self.absolute_check.isChecked():
                values = np.abs(k)
            curve.setData(c.m_norm,values,connect="finite")
            curve.setVisible(check.isChecked())
        self.plot.disableAutoRange()
        if self.sender() in (self.ps_check,self.ss_check,self.absolute_check,self.radius_check):
            install_plot_fit(self.plot).request()
