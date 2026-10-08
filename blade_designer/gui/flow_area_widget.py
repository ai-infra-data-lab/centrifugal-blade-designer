"""Gross-area context plot, station ratios and linked cross-flow cursor."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QTableWidget,QTableWidgetItem,QLabel,QAbstractItemView
from .plot_widgets import configure_plot

class FlowAreaWidget(QWidget):
    stationChosen=Signal(object)
    def __init__(self):
        super().__init__()
        self.result=None;self.parameters=None
        layout=QHBoxLayout(self)
        self.plot=pg.PlotWidget(background="#101c2b")
        configure_plot(self.plot,"Normalized Flow Meridional","Gross Flow Area [mm²]")
        self.curve=self.plot.plot(pen=pg.mkPen("#56d9e0",width=2),connect="finite")
        self.cursor=self.plot.plot(pen=None,symbol="o",symbolBrush="#ffe477",symbolSize=10)
        self.markers=[]
        for name in ("IMP_LE","IMP_TE","DIF_LE","DIF_TE"):
            line=pg.InfiniteLine(angle=90,pen=pg.mkPen("#909cac"),label=name.replace("_"," "),
                                 labelOpts={"position":.92 if len(self.markers)%2==0 else .75})
            self.plot.addItem(line);self.markers.append(line)
        layout.addWidget(self.plot,3)
        side=QWidget();rows=QVBoxLayout(side)
        self.table=QTableWidget(6,3)
        self.table.setHorizontalHeaderLabels(["Station","Area [mm²]","A / A_IMP_LE"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True);self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setMinimumHeight(170);self.table.setMaximumHeight(180)
        self.table.cellClicked.connect(self._table_selected);rows.addWidget(self.table)
        self.info=QLabel("Select a station or move the cursor over the area plot.")
        self.info.setWordWrap(True);self.info.setMinimumHeight(54);rows.addWidget(self.info)
        self.errors=QLabel();self.errors.setWordWrap(True);rows.addWidget(self.errors)
        layout.addWidget(side,2)
        self.plot.scene().sigMouseMoved.connect(self._mouse_moved)
        self.plot.disableAutoRange()

    def update_result(self,result,parameters):
        self.result=result;self.parameters=parameters
        positions=np.array([s.m_flow_norm for s in result.stations])
        areas=np.array([s.gross_area for s in result.stations])
        # Graphics-only separators prevent joining across unavailable sections.
        invalid=[float(e.split(":")[0].split("=")[1]) for e in result.errors]
        all_positions=np.r_[positions,invalid];all_areas=np.r_[areas,np.full(len(invalid),np.nan)]
        order=np.argsort(all_positions)
        self.curve.setData(all_positions[order],all_areas[order],connect="finite")
        for marker,name in zip(self.markers,("IMP_LE","IMP_TE","DIF_LE","DIF_TE")):
            marker.setPos(next(s.m_flow_norm for s in parameters.stations if s.kind.value==name))
        for row,parameter in enumerate(parameters.stations):
            station=result.named_stations[parameter.kind.value]
            ratio=None if station is None else result.area_ratio(station)
            values=[parameter.kind.value,"N/A" if station is None else f"{station.gross_area:.8g}",
                    "N/A" if ratio is None else f"{ratio:.6g}"]
            for col,value in enumerate(values):self.table.setItem(row,col,QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        self.errors.setText("" if not result.errors else f"Area unavailable at {len(result.errors)} positions; see validation status.")
        self.errors.setVisible(bool(result.errors))
        self.errors.setToolTip("\n".join(result.errors))
        self.cursor.setData([],[])
        self.info.setText("Select a station or move the cursor over the area plot.")

    def select_position(self,position,exact=False):
        if self.result is None or not self.result.stations:return
        if exact:
            missing=next((p.kind.value for p in self.parameters.stations if p.m_flow_norm==position and self.result.named_stations[p.kind.value] is None),None)
            if missing:
                self.cursor.setData([],[]);self.info.setText(f"{missing}: cross-flow intersection unavailable.");return
        station=min(self.result.stations,key=lambda p:abs(p.m_flow_norm-position))
        self.cursor.setData([station.m_flow_norm],[station.gross_area])
        self.info.setText(f"m_flow_norm = {station.m_flow_norm:.6g} | m = {station.m:.6g} mm\n"
                          f"{station.component_region} | A = {station.gross_area:.8g} mm²\n"
                          f"Hub R = {station.hub_r:.6g} | Shroud R = {station.shroud_r:.6g} | L_hs = {station.passage_length:.6g} mm")
        self.stationChosen.emit(station)

    def _table_selected(self,row,column):
        if self.parameters is not None:self.select_position(self.parameters.stations[row].m_flow_norm,exact=True)

    def _mouse_moved(self,position):
        if self.plot.sceneBoundingRect().contains(position):
            p=self.plot.getViewBox().mapSceneToView(position)
            if 0<=p.x()<=1:self.select_position(p.x())

    def fit_view(self):
        self.plot.autoRange();self.plot.disableAutoRange()
