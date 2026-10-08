from copy import deepcopy
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QFormLayout,
    QTableWidget,QPushButton,QLabel,QTableWidgetItem,QAbstractItemView)
from .control_point_editor import CompactDoubleSpinBox
from .context_meridional import ContextMeridional
from .plot_widgets import configure_plot
from ..models.flow_path import FlowPathParameters, StationType
from ..geometry.flow_path import validate_component_stations
from ..models.meridional import (MeridionalCurveParameters,default_shroud,
    LineSegmentParameters,ArcSegmentParameters)
from ..geometry.meridional_segments import generate_meridional,validate_flow_path


class MeridionalEditor(QWidget):
    parametersChanged = Signal()
    stationsChanged = Signal()
    editFinished = Signal()

    def __init__(self):
        super().__init__()
        self.mean_points=4001
        self.flow_path=FlowPathParameters()
        self._loading=False
        self.curves=[MeridionalCurveParameters(),default_shroud()]
        layout=QVBoxLayout(self)
        self.selector=QComboBox();self.selector.addItems(["Hub","Shroud"])
        layout.addWidget(self.selector)
        form=QFormLayout();layout.addLayout(form)
        self.start_controls={}
        for name,label in (("start_z","Start Z"),("start_r","Start R"),("start_angle_deg","Start angle [deg]")):
            box=CompactDoubleSpinBox();box.setDecimals(12);box.setRange(-1e9,1e9)
            self.start_controls[name]=box;form.addRow(label,box)
            box.valueChanged.connect(lambda value,key=name:self._start_changed(key,value))
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(["Type","Length","Radius","Sweep [deg]","Direction"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(170);layout.addWidget(self.table)
        row=QHBoxLayout();layout.addLayout(row)
        for label,callback in (("Add Line",lambda:self.add_segment(False)),("Add Arc",lambda:self.add_segment(True)),
                ("Delete",self.delete_segment),("Move Up",lambda:self.move_segment(-1)),("Move Down",lambda:self.move_segment(1))):
            button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
        layout.addWidget(QLabel("Component Stations — Normalized Flow Meridional"))
        self.station_table=QTableWidget(6,2)
        self.station_table.setHorizontalHeaderLabels(["Station","m_flow_norm"])
        self.station_table.setMaximumHeight(210)
        layout.addWidget(self.station_table)
        self.set_stations(self.flow_path)
        from .blade_edge_editor import BladeEdgeEditor
        self.blade_edges=BladeEdgeEditor();layout.addWidget(self.blade_edges)
        self.blade_edges.parametersChanged.connect(self.parametersChanged)
        self.blade_edges.editFinished.connect(self.editFinished)
        self.context=ContextMeridional()
        self.plot=self.context.plot
        self.items=self.context.curves
        self.joins=[self.plot.plot(pen=None,symbol="o",symbolSize=6,symbolBrush=color) for color in ("#56d9e0","#eead72")]
        layout.addWidget(self.context,1);self.message=QLabel();self.message.setWordWrap(True);layout.addWidget(self.message)
        self.selector.currentIndexChanged.connect(self._curve_selected)
        self._populate();self.update_preview();self.fit_view()

    def _curve_selected(self):
        self.editFinished.emit();self._populate()

    def get_stations(self):return deepcopy(self.flow_path)

    def set_stations(self,parameters):
        self.flow_path=deepcopy(parameters)
        for row,station in enumerate(self.flow_path.stations):
            self.station_table.setItem(row,0,QTableWidgetItem(station.kind.value))
            box=CompactDoubleSpinBox();box.setDecimals(12);box.setRange(0,1);box.setSingleStep(.01)
            box.setValue(station.m_flow_norm);box.setEnabled(row not in (0,5))
            box.valueChanged.connect(lambda value,i=row:self._station_changed(i,value))
            self.station_table.setCellWidget(row,1,box)
        self.station_table.resizeColumnsToContents()

    def _station_changed(self,row,value):
        self.flow_path.stations[row].m_flow_norm=value
        try:validate_component_stations(self.flow_path);self.message.setText("Station order valid")
        except ValueError as exc:self.message.setText(f"ERROR: {exc}")
        self.update_preview();self.stationsChanged.emit();self.parametersChanged.emit()

    def get_curves(self): return deepcopy(self.curves)

    def set_curves(self,hub,shroud):
        self.curves=deepcopy([hub,shroud]);self._populate();self.update_preview()

    def _populate(self):
        self._loading=True
        curve=self.curves[self.selector.currentIndex()]
        for key,box in self.start_controls.items(): box.setValue(getattr(curve,key))
        self.table.setRowCount(len(curve.segments))
        for row,seg in enumerate(curve.segments):
            arc=isinstance(seg,ArcSegmentParameters)
            self.table.setItem(row,0,QTableWidgetItem("Arc" if arc else "Line"))
            self.table.item(row,0).setFlags(self.table.item(row,0).flags() & ~self.table.item(row,0).flags().ItemIsEditable)
            for col,key in ((1,"length"),(2,"radius"),(3,"sweep_deg")):
                self.table.removeCellWidget(row,col)
                self.table.setItem(row,col,QTableWidgetItem(""))
                if hasattr(seg,key):
                    box=CompactDoubleSpinBox();box.setDecimals(12);box.setRange(-1e9,1e9);box.setValue(getattr(seg,key))
                    box.valueChanged.connect(lambda value,i=row,k=key:self._segment_changed(i,k,value))
                    self.table.setCellWidget(row,col,box)
            self.table.removeCellWidget(row,4)
            if arc:
                direction=QComboBox();direction.addItems(["CCW","CW"]);direction.setCurrentIndex(int(seg.clockwise))
                direction.currentIndexChanged.connect(lambda value,i=row:self._segment_changed(i,"clockwise",bool(value)))
                self.table.setCellWidget(row,4,direction)
        self.table.resizeColumnsToContents();self._loading=False

    def _start_changed(self,key,value):
        if self._loading:return
        setattr(self.curves[self.selector.currentIndex()],key,value);self._changed()

    def _segment_changed(self,row,key,value):
        if self._loading:return
        setattr(self.curves[self.selector.currentIndex()].segments[row],key,value);self._changed()

    def _changed(self):
        self.update_preview();self.parametersChanged.emit()

    def add_segment(self,arc):
        self.curves[self.selector.currentIndex()].segments.append(ArcSegmentParameters() if arc else LineSegmentParameters())
        self._populate();self.table.selectRow(self.table.rowCount()-1);self._changed();self.editFinished.emit()

    def delete_segment(self):
        segments=self.curves[self.selector.currentIndex()].segments;row=self.table.currentRow()
        if 0<=row<len(segments):
            del segments[row];self._populate();self._changed();self.editFinished.emit()

    def move_segment(self,delta):
        segments=self.curves[self.selector.currentIndex()].segments;row=self.table.currentRow();other=row+delta
        if 0<=row<len(segments) and 0<=other<len(segments):
            segments[row],segments[other]=segments[other],segments[row]
            self._populate();self.table.selectRow(other);self._changed();self.editFinished.emit()

    def update_preview(self):
        try:
            geometry=[generate_meridional(p) for p in self.curves];validate_flow_path(*geometry)
            from types import SimpleNamespace
            g=SimpleNamespace(hub=geometry[0],shroud=geometry[1])
            self.context.update_geometry(g,self.flow_path,self.mean_points)
            if hasattr(self,'blade_edges'):
                from ..models.parameters import BladeParameters
                p=BladeParameters();self.blade_edges.apply_to(p)
                self.context.update_blade_edges(g,p)
            for g,item,joins in zip(geometry,self.items,self.joins):
                item.setData(g.z,g.r)
                points=np.array([g.segments[0].start.zr]+[s.end.zr for s in g.segments])
                joins.setData(points[:,0],points[:,1])
            self.message.setText("G1 continuous • angle measured from +Z toward +R")
        except (ValueError,ArithmeticError) as exc:self.message.setText(f"ERROR: {exc} — showing last valid curves")
        self.plot.disableAutoRange()

    def fit_view(self): self.plot.autoRange();self.plot.disableAutoRange()
