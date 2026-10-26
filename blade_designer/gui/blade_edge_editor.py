"""Physical R/Z endpoint input; normalized arclength remains the storage API."""
from copy import deepcopy
from PySide6.QtCore import Signal,Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QTableWidget,QTableWidgetItem,QPushButton,QAbstractItemView
from .control_point_editor import CompactDoubleSpinBox
from ..models.parameters import BladeParameters
from ..geometry.meridional_segments import generate_meridional
from ..geometry.blade_edge import edge_endpoints,project_to_wall
from ..geometry.row_coordinates import build_row_coordinates

class BladeEdgeEditor(QWidget):
    parametersChanged=Signal()
    editFinished=Signal()

    def __init__(self):
        super().__init__();layout=QVBoxLayout(self)
        label=QLabel("Blade Edges — R / Z [mm]\nRとZを入力して適用。対応する壁面上の最近点へ投影します。")
        label.setWordWrap(True);layout.addWidget(label)
        self.scale_label=QLabel();self.scale_label.setWordWrap(True);layout.addWidget(self.scale_label)
        self.coordinate_map=None;self.coordinate_error="";self.row_positions={};self.position_items={}
        self.table=QTableWidget(8,5);self.table.setHorizontalHeaderLabels(["Row","Wall / Edge","R [mm]","Z [mm]","翼列距離 s"])
        self.table.horizontalHeader().moveSection(4,2)
        self.table.setMinimumHeight(275);self.table.setMaximumHeight(310)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table);self.controls={};self.coordinate_controls={}
        self.row_edges={};self.row_controls={};self.all_coordinate_controls={}
        self.all_display_coordinates={};self._group_order=[];self._names={};self._fields={}
        self.apply_button=QPushButton("R/Zを適用 / Apply R/Z")
        self.apply_button.clicked.connect(self.apply_coordinates);layout.addWidget(self.apply_button)
        self.set_parameters(BladeParameters())

    def _rebuild_controls(self):
        for box in self.row_controls.values():box.deleteLater()
        self.table.setRowCount(0)
        self.row_controls={};self.all_coordinate_controls={};self.all_display_coordinates={}
        self.position_items={}
        self.table.setRowCount(4*len(self._group_order));row=0
        for key in self._group_order:
            for side,wall in (("leading_edge","hub"),("leading_edge","shroud"),("trailing_edge","hub"),("trailing_edge","shroud")):
                self.table.setItem(row,0,QTableWidgetItem(self._names[key]))
                self.table.setItem(row,1,QTableWidgetItem(f"{'Hub' if wall=='hub' else 'Shroud'} {'LE' if side=='leading_edge' else 'TE'}"))
                for column,axis in ((2,"r"),(3,"z")):
                    coordinate=CompactDoubleSpinBox();coordinate.setDecimals(12)
                    coordinate.setRange(0 if axis=="r" else -1e9,1e9);coordinate.setSingleStep(.1)
                    self.all_coordinate_controls[key,side,wall,axis]=coordinate
                    self.table.setCellWidget(row,column,coordinate)
                item=QTableWidgetItem('—');item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.position_items[key,side,wall]=item;self.table.setItem(row,4,item)
                # Retain the normalized programmatic API, outside the visible UI.
                box=CompactDoubleSpinBox(self);box.setDecimals(12);box.setRange(0,1);box.setSingleStep(.01);box.hide()
                self.row_controls[key,side,wall]=box
                box.valueChanged.connect(lambda value,k=key,s=side,w=wall:self._changed(k,s,w,value))
                box.editingFinished.connect(self.editFinished)
                row+=1

    def set_parameters(self,params):
        self._has_row_list=params.blade_rows is not None
        params=deepcopy(params)
        if params.blade_rows is not None:params.blade_rows=[row for row in params.blade_rows if row.kind!='meridional']
        previous=list(self._group_order)
        self._legacy_edges={k:deepcopy(getattr(params,k)) for k in ("impeller_edges","diffuser_edges")}
        self._active_row=params.active_blade_row
        self.row_edges={row.identifier:deepcopy(getattr(row.parameters,row.kind+"_edges")) for row in params.blade_rows or []}
        self._group_order=list(self.row_edges) if params.blade_rows is not None else list(self._legacy_edges)
        self._names={row.identifier:row.name for row in params.blade_rows or []} if params.blade_rows is not None else {"impeller_edges":"Impeller","diffuser_edges":"Diffuser"}
        self._fields={row.identifier:row.kind+"_edges" for row in params.blade_rows or []} if params.blade_rows is not None else {k:k for k in self._legacy_edges}
        if previous!=self._group_order:self._rebuild_controls()
        try:
            self.walls=(generate_meridional(params.hub),generate_meridional(params.shroud))
        except (ValueError,ArithmeticError):
            pass  # invalid wall edits retain the last valid projection geometry
        self.set_coordinate_curves([params.hub,params.shroud])
        self._sync_controls()
        self.table.resizeColumnsToContents()

    def set_walls(self,hub,shroud):
        self.walls=(hub,shroud);self._sync_controls()

    def set_row_names(self,rows,identifier):
        rows=[row for row in rows if row.kind!='meridional']
        self._active_row=identifier
        if self.row_edges:
            order=[row.identifier for row in rows]
            pending={key:box.value() for key,box in self.all_coordinate_controls.items()
                     if box.value()!=self.all_display_coordinates[key]}
            self._names={row.identifier:row.name for row in rows}
            self._fields={row.identifier:row.kind+"_edges" for row in rows}
            self.row_edges={row.identifier:self.row_edges[row.identifier] if row.identifier in self.row_edges
                            else deepcopy(getattr(row.parameters,row.kind+"_edges")) for row in rows}
            if order!=self._group_order:
                self._group_order=order;self._rebuild_controls();self._sync_controls()
                for key,value in pending.items():
                    if key in self.all_coordinate_controls:self.all_coordinate_controls[key].setValue(value)
        self._refresh_coordinate_map()
        self._sync_aliases()
        for index,key in enumerate(self._group_order):
            for offset in range(4):
                item=self.table.item(4*index+offset,0)
                item.setText(self._names[key]);item.setToolTip(self._names[key])
        self.table.resizeColumnsToContents()

    def set_coordinate_curves(self,curves):
        self._coordinate_curves=deepcopy(curves);self._refresh_coordinate_map()

    def clear_coordinate_map(self,message):
        self.coordinate_map=None;self.coordinate_error=message;self._sync_positions()

    def _refresh_coordinate_map(self):
        try:
            self.coordinate_map=build_row_coordinates(self._coordinate_curves,self._group_order)
            self.coordinate_error=''
        except (ValueError,ArithmeticError) as exc:
            self.coordinate_map=None;self.coordinate_error=str(exc)
        self._sync_positions()

    def _sync_positions(self):
        self.row_positions={}
        if self.coordinate_map is None:
            self.scale_label.setText('翼列距離 s: 未設定 — '+self.coordinate_error)
        else:
            self.scale_label.setText('子午面の翼列距離 s: '+'  |  '.join(
                f'{i}–{i+1} {self._names[key]}' for i,key in enumerate(self.coordinate_map.order)))
        for key,item in self.position_items.items():self._sync_position(*key)

    def _sync_position(self,key,side,wall):
        item=self.position_items.get((key,side,wall))
        if item is None:return
        item.setData(Qt.ItemDataRole.ForegroundRole,None)
        if self.coordinate_map is None:
            item.setText('—');item.setToolTip(self.coordinate_error);return
        try:
            value=self.coordinate_map.position(key,wall,getattr(getattr(self._primary_edges()[key],side),wall+'_m_flow_norm'))
            offset=self.coordinate_map.order.index(key)
            self.row_positions[key,side,wall]=value
            outside=value<offset-1e-10 or value>offset+1+1e-10
            item.setText(f'{value:.8g}')
            item.setToolTip(f's = {value:.12g}\n翼列内位置 = {value-offset:.12g}（範囲 {offset}–{offset+1}）'
                            +('\n所属翼列の範囲外です。' if outside else ''))
            if outside:item.setForeground(QColor('#dc6868'))
        except (ValueError,KeyError) as exc:
            item.setText('—');item.setToolTip(str(exc))

    def _primary_edges(self):return self.row_edges if self._has_row_list else self._legacy_edges

    def edge_groups(self):return [(key,self._names[key],self._primary_edges()[key]) for key in self._group_order]

    def all_edges(self):
        if self._has_row_list and not self._group_order:return []
        result=list(self._primary_edges().values())
        for edges in self.edges.values():
            if all(edges is not item for item in result):result.append(edges)
        return result

    def _sync_aliases(self):
        self._aliases={}
        for field in self._legacy_edges:
            candidates=[key for key in self._group_order if self._fields[key]==field]
            if candidates:self._aliases[field]=self._active_row if self._active_row in candidates else candidates[0]
        self.edges={field:self._primary_edges()[self._aliases[field]] if field in self._aliases else edges
                    for field,edges in self._legacy_edges.items()}
        self.controls={};self.coordinate_controls={};self._display_coordinates={}
        for field,key in self._aliases.items():
            for (group,side,wall),box in self.row_controls.items():
                if group==key:self.controls[field,side,wall]=box
            for (group,side,wall,axis),box in self.all_coordinate_controls.items():
                if group==key:
                    index=(field,side,wall,axis);self.coordinate_controls[index]=box
                    self._display_coordinates[index]=self.all_display_coordinates.get((group,side,wall,axis),box.value())

    def _sync_controls(self):
        for (key,side,wall),box in self.row_controls.items():
            box.blockSignals(True);box.setValue(getattr(getattr(self._primary_edges()[key],side),wall+"_m_flow_norm"));box.blockSignals(False)
            self._sync_coordinate(key,side,wall)
        self._sync_aliases()

    def _sync_coordinate(self,key,side,wall):
        points=edge_endpoints(getattr(self._primary_edges()[key],side),*self.walls)
        z,r=points[0 if wall=="hub" else 1]
        for axis,value in (("r",r),("z",z)):
            index=(key,side,wall,axis);box=self.all_coordinate_controls[index]
            box.blockSignals(True);box.setValue(float(value));box.blockSignals(False)
            self.all_display_coordinates[index]=box.value()
        self._sync_position(key,side,wall)

    def apply_to(self,params):
        for key,edges in self.edges.items():setattr(params,key,deepcopy(edges))

    def apply_to_rows(self,rows):
        for row in rows or []:
            if row.identifier in self.row_edges:setattr(row.parameters,row.kind+"_edges",deepcopy(self.row_edges[row.identifier]))

    def _changed(self,key,side,wall,value):
        key=self._aliases.get(key,key)
        setattr(getattr(self._primary_edges()[key],side),wall+"_m_flow_norm",value)
        self._sync_coordinate(key,side,wall);self._sync_aliases();self.parametersChanged.emit()

    def apply_coordinates(self):
        updates=[]
        for key,side,wall in self.row_controls:
            indices=[(key,side,wall,axis) for axis in ("z","r")]
            if any(self.all_coordinate_controls[i].value()!=self.all_display_coordinates[i] for i in indices):
                zr=[self.all_coordinate_controls[i].value() for i in indices]
                fraction,_=project_to_wall(self.walls[0 if wall=="hub" else 1],zr)
                updates.append((key,side,wall,fraction))
        if not updates:return
        for key,side,wall,value in updates:
            setattr(getattr(self._primary_edges()[key],side),wall+"_m_flow_norm",value)
        self._sync_controls();self.parametersChanged.emit();self.editFinished.emit()

    def move_endpoint(self,key,side,wall,value):
        # Drag projection retains full float64 precision; formatting is UI only.
        self._changed(key,side,wall,value)
        key=self._aliases.get(key,key)
        box=self.row_controls[key,side,wall];box.blockSignals(True);box.setValue(value);box.blockSignals(False)
