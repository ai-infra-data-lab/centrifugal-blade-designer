from copy import deepcopy
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QFormLayout,
    QTableWidget,QPushButton,QLabel,QTableWidgetItem,QAbstractItemView)
from .control_point_editor import CompactDoubleSpinBox
from .context_meridional import ContextMeridional
from ..models.flow_path import FlowPathParameters
from ..geometry.flow_path import validate_component_stations
from ..models.meridional import (MeridionalCurveParameters,default_shroud,
    LineSegmentParameters,ArcSegmentParameters)
from ..geometry.meridional_segments import generate_meridional,validate_flow_path,convert_segment_type
from ..geometry.blade_edge import rescale_extended_wall_edges,adapt_wall_edge_coordinates


class MeridionalEditor(QWidget):
    parametersChanged = Signal()
    stationsChanged = Signal()
    editFinished = Signal()
    ownershipChanged = Signal()
    wallExtended = Signal(str,float,float)

    def __init__(self):
        super().__init__()
        self.mean_points=4001
        self.flow_path=FlowPathParameters()
        self._loading=False
        self.curves=[MeridionalCurveParameters(),default_shroud()]
        self.blade_rows = []
        self.additional_edges = lambda: []
        self.ownership_items = []
        layout=QVBoxLayout(self)
        self.selector=QComboBox();self.selector.addItems(["Hub","Shroud"])
        layout.addWidget(self.selector)
        form=QFormLayout();layout.addLayout(form)
        self.start_controls={}
        for name,label in (("start_z","Start Z"),("start_r","Start R"),("start_angle_deg","Start angle [deg]")):
            box=CompactDoubleSpinBox();box.setDecimals(12);box.setRange(-1e9,1e9)
            box.setKeyboardTracking(False)
            self.start_controls[name]=box;form.addRow(label,box)
            box.valueChanged.connect(lambda value,key=name:self._start_changed(key,value))
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(["Type","Length","Radius","Sweep [deg]","Direction","所属翼列 / Blade Row"])
        self.table.horizontalHeader().moveSection(5, 1)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(170);layout.addWidget(self.table)
        row=QHBoxLayout();layout.addLayout(row)
        for label,callback in (("Add Line",lambda:self.add_segment(False)),("Add Arc",lambda:self.add_segment(True)),
                ("Delete",self.delete_segment),("Move Up",lambda:self.move_segment(-1)),("Move Down",lambda:self.move_segment(1))):
            button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
        # Retain the legacy station API/data for project and Flow Area compatibility.
        # The station editor is no longer part of the visible GUI.
        self.station_table=QTableWidget(6,2,self)
        self.station_table.setHorizontalHeaderLabels(["Station","m_flow_norm"])
        self.station_table.setMaximumHeight(210)
        self.station_table.hide()
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

    def set_blade_rows(self, rows):
        choices = [(row.identifier, row.name) for row in rows]
        if choices == self.blade_rows: return
        self.blade_rows = choices
        self._populate()
        self.update_preview()

    def _ownership_changed(self, row, identifier):
        if self._loading: return
        self.curves[self.selector.currentIndex()].segments[row].blade_row = identifier
        self.ownershipChanged.emit()
        self._changed()
        self.editFinished.emit()

    def _show_ownership(self, geometries):
        from ..geometry.meridional_segments import evaluate_segment
        for item in self.ownership_items: self.plot.removeItem(item)
        self.ownership_items = []
        colors = ("#89ef85", "#f896c6", "#b4a3ff", "#f6e16a", "#79baff")
        names = {identifier: (name, colors[i % len(colors)]) for i, (identifier, name) in enumerate(self.blade_rows)}
        for curve, geometry in zip(self.curves, geometries):
            for i, (definition, segment) in enumerate(zip(curve.segments, geometry.segments)):
                if definition.blade_row is None: continue
                name, color = names.get(definition.blade_row, (definition.blade_row, "#ff6666"))
                points = evaluate_segment(segment, np.linspace(0, segment.length, 33))
                line = self.plot.plot(points[:,0], points[:,1], pen=pg.mkPen(color, width=4))
                line.setToolTip(f"{name} • segment {i + 1}")
                text = pg.TextItem(f"{name} [{i + 1}]", color=color, anchor=(0,1))
                text.setPos(*points[len(points)//2]);self.plot.addItem(text, ignoreBounds=True)
                self.ownership_items.extend((line, text))

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
            kind=QComboBox();kind.addItem("Line",False);kind.addItem("Arc",True)
            kind.setCurrentIndex(int(arc))
            kind.currentIndexChanged.connect(lambda index,i=row:self._type_changed(i,bool(index)))
            self.table.setCellWidget(row,0,kind)
            for col,key in ((1,"length"),(2,"radius"),(3,"sweep_deg")):
                self.table.removeCellWidget(row,col)
                self.table.setItem(row,col,QTableWidgetItem(""))
                if hasattr(seg,key):
                    box=CompactDoubleSpinBox();box.setDecimals(12);box.setRange(-1e9,1e9);box.setValue(getattr(seg,key))
                    box.setKeyboardTracking(False)
                    box.valueChanged.connect(lambda value,i=row,k=key:self._segment_changed(i,k,value))
                    self.table.setCellWidget(row,col,box)
            self.table.removeCellWidget(row,4)
            if arc:
                direction=QComboBox();direction.addItems(["CCW","CW"]);direction.setCurrentIndex(int(seg.clockwise))
                direction.currentIndexChanged.connect(lambda value,i=row:self._segment_changed(i,"clockwise",bool(value)))
                self.table.setCellWidget(row,4,direction)
            owner=QComboBox();owner.addItem("未割り当て / Unassigned", None)
            for identifier,name in self.blade_rows: owner.addItem(name, identifier)
            owner.setCurrentIndex(max(0, owner.findData(seg.blade_row)))
            owner.setToolTip("This complete line/arc belongs to the selected blade row's export domain.")
            owner.currentIndexChanged.connect(lambda index,i=row,box=owner:self._ownership_changed(i,box.currentData()))
            self.table.setCellWidget(row,5,owner)
        self.table.resizeColumnsToContents();self._loading=False

    def _start_changed(self,key,value):
        if self._loading:return
        curve=deepcopy(self.curves[self.selector.currentIndex()]);setattr(curve,key,value)
        self._edit_wall(curve)

    def _edit_wall(self,curve,refresh=False,row=None):
        index=self.selector.currentIndex();wall="hub" if index==0 else "shroud"
        pending={key:box.value() for key,box in self.blade_edges.all_coordinate_controls.items()
                 if box.value()!=self.blade_edges.all_display_coordinates[key]}
        sources=self.blade_edges.all_edges()+self.additional_edges()
        try:
            old=generate_meridional(self.curves[index]);new=generate_meridional(curve)
            geometries=[generate_meridional(p) for p in self.curves];geometries[index]=new
            validate_flow_path(*geometries)
            proposals=[adapt_wall_edge_coordinates(edges,wall,old,new) for edges in sources]
        except (ValueError,ArithmeticError) as exc:
            self._populate()
            if row is not None:self.table.selectRow(row)
            self.message.setText(f"ERROR: 無効な子午面のため編集を取り消しました: {exc}")
            return False
        self.curves[index]=curve
        for edges,proposal in zip(sources,proposals):
            edges.leading_edge=proposal.leading_edge;edges.trailing_edge=proposal.trailing_edge
        self.blade_edges.set_walls(*geometries)
        if refresh:self._populate()
        if row is not None:self.table.selectRow(row)
        self._changed()
        for key,value in pending.items():self.blade_edges.all_coordinate_controls[key].setValue(value)
        return True

    def _type_changed(self,row,arc):
        if self._loading:return
        curve=self.curves[self.selector.currentIndex()];segment=curve.segments[row]
        if isinstance(segment,ArcSegmentParameters)==arc:return
        try:replacement=convert_segment_type(segment,arc)
        except ValueError as exc:
            self._populate();self.message.setText(f"ERROR: {exc}");return
        curve=deepcopy(curve);curve.segments[row]=replacement
        if self._edit_wall(curve,refresh=True,row=row):self.editFinished.emit()

    def _segment_changed(self,row,key,value):
        if self._loading:return
        curve=deepcopy(self.curves[self.selector.currentIndex()]);setattr(curve.segments[row],key,value)
        self._edit_wall(curve,row=row)

    def _changed(self):
        self.update_preview();self.parametersChanged.emit()

    def add_segment(self,arc):
        index=self.selector.currentIndex();curve=self.curves[index]
        pending={key:box.value() for key,box in self.blade_edges.all_coordinate_controls.items()
                 if box.value()!=self.blade_edges.all_display_coordinates[key]}
        try:old_length=generate_meridional(curve).length
        except (ValueError,ArithmeticError):old_length=None
        curve.segments.append(ArcSegmentParameters() if arc else LineSegmentParameters())
        if old_length is not None:
            try:new_wall=generate_meridional(curve)
            except (ValueError,ArithmeticError):new_wall=None
            if new_wall is not None:
                wall="hub" if index==0 else "shroud"
                for edges in self.blade_edges.all_edges():
                    rescale_extended_wall_edges(edges,wall,old_length,new_wall.length)
                walls=list(self.blade_edges.walls);walls[index]=new_wall
                self.blade_edges.set_walls(*walls)
                self.wallExtended.emit(wall,old_length,new_wall.length)
        self._populate();self.table.selectRow(self.table.rowCount()-1);self._changed()
        for key,value in pending.items():self.blade_edges.all_coordinate_controls[key].setValue(value)
        self.editFinished.emit()

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
            self.blade_edges.set_walls(*geometry)
            self._show_ownership(geometry)
            from types import SimpleNamespace
            g=SimpleNamespace(hub=geometry[0],shroud=geometry[1])
            self.context.update_geometry(g,self.flow_path,self.mean_points)
            if hasattr(self,'blade_edges'):
                self.context.update_edge_groups(g,self.blade_edges.edge_groups())
            for g,item,joins in zip(geometry,self.items,self.joins):
                item.setData(g.z,g.r)
                points=np.array([g.segments[0].start.zr]+[s.end.zr for s in g.segments])
                joins.setData(points[:,0],points[:,1])
            self.message.setText("G1 continuous • angle measured from +Z toward +R")
        except (ValueError,ArithmeticError) as exc:self.message.setText(f"ERROR: {exc} — showing last valid curves")
        self.plot.disableAutoRange()

    def fit_view(self): self.plot.autoRange();self.plot.disableAutoRange()
