import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QAbstractItemView
from ..models.geometry import BladeGeometry
from ..geometry.pitch import linear_pitch
from .plot_widgets import configure_plot


class MetricsWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        right=QWidget();right_layout=QVBoxLayout(right)
        self.table = QTableWidget(0,2)
        self.table.setHorizontalHeaderLabels(["Metric","Value"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0,320)
        self.table.setMinimumHeight(140)
        layout.addWidget(self.table,1)
        self.choice = QComboBox()
        self.choice.addItems(["Pitch","Local Solidity"])
        self.choice.currentIndexChanged.connect(self._refresh_plot)
        right_layout.addWidget(self.choice)
        self.plot = pg.PlotWidget(background="#101c2b")
        self.plot.setMinimumHeight(140)
        configure_plot(self.plot,"Normalized Meridional","Pitch [mm]")
        self.curve = self.plot.plot(pen=pg.mkPen("#56d9e0",width=2))
        right_layout.addWidget(self.plot,1)
        layout.addWidget(right,2)
        self.geometry: BladeGeometry | None = None
        self.vane_count = 20

    def update_geometry(self, geometry: BladeGeometry, vane_count: int) -> None:
        self.geometry, self.vane_count = geometry,vane_count
        m = geometry.metrics
        throat = m.throat
        rows = [
            ("Blade Count",vane_count),("Angular Pitch [deg]",m.angular_pitch_deg),
            ("LE Linear Pitch [mm]",m.pitch_le),("Mid-Meridional Pitch [mm]",m.pitch_mid),("TE Linear Pitch [mm]",m.pitch_te),
            ("Physical Chord [mm]",m.chord),("Camber Length [mm]",m.camber_length),
            ("Solidity @ Mnorm=0.5",m.solidity_mid),("C/S @ LE",m.solidity_le),("C/S @ M50",m.solidity_mid),("C/S @ TE",m.solidity_te),
            ("Throat [mm]",None if throat is None else throat.width),
            ("Throat / Pitch",m.throat_pitch_ratio),
            ("Maximum |PS Curvature| [1/mm]",float(np.max(np.abs(geometry.curvature.ps_curvature)))),
            ("Maximum |SS Curvature| [1/mm]",float(np.max(np.abs(geometry.curvature.ss_curvature)))),
            ("Resolved PS Mapping",geometry.resolved_mapping.value),
            ("Throat segments","N/A" if throat is None else throat.blade1_segment+" → adjacent "+throat.blade2_segment)]
        self.table.setRowCount(len(rows))
        for i,(label,value) in enumerate(rows):
            self.table.setItem(i,0,QTableWidgetItem(label))
            text = "N/A (no adjacent blade)" if value is None else f"{value:.9g}" if isinstance(value,(float,int)) else value
            self.table.setItem(i,1,QTableWidgetItem(text))
        self._refresh_plot()

    def _refresh_plot(self) -> None:
        if self.geometry is None:
            return
        b = self.geometry
        pitch = linear_pitch(b.camber.r,self.vane_count)
        values = pitch if self.choice.currentIndex() == 0 else b.metrics.chord/pitch
        self.plot.setLabel("left","Pitch [mm]" if self.choice.currentIndex() == 0 else "Local Solidity")
        self.curve.setData(b.camber.m_norm,values)
        self.plot.disableAutoRange()
