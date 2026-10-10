"""Independent Hub/Shroud blade row endpoints (normalized wall arclength)."""
from copy import deepcopy
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QTableWidget,QTableWidgetItem
from .control_point_editor import CompactDoubleSpinBox
from ..models.parameters import BladeParameters

class BladeEdgeEditor(QWidget):
    parametersChanged=Signal()
    editFinished=Signal()

    def __init__(self):
        super().__init__();layout=QVBoxLayout(self)
        layout.addWidget(QLabel("Blade Edges\nValues: normalized physical distance along each wall"))
        self.table=QTableWidget(2,5);self.table.setHorizontalHeaderLabels(["Row","Hub LE","Shroud LE","Hub TE","Shroud TE"])
        self.table.setMaximumHeight(125);layout.addWidget(self.table);self.controls={}
        for row,key in enumerate(("impeller_edges","diffuser_edges")):
            self.table.setItem(row,0,QTableWidgetItem("IMP" if row==0 else "DIF"))
            for column,(side,wall) in enumerate((("leading_edge","hub"),("leading_edge","shroud"),("trailing_edge","hub"),("trailing_edge","shroud")),1):
                box=CompactDoubleSpinBox();box.setDecimals(12);box.setRange(0,1);box.setSingleStep(.01)
                self.controls[key,side,wall]=box
                box.valueChanged.connect(lambda value,k=key,s=side,w=wall:self._changed(k,s,w,value))
                box.editingFinished.connect(self.editFinished)
                self.table.setCellWidget(row,column,box)
        self.set_parameters(BladeParameters())

    def set_parameters(self,params):
        self.edges={k:deepcopy(getattr(params,k)) for k in ("impeller_edges","diffuser_edges")}
        for (key,side,wall),box in self.controls.items():
            box.blockSignals(True);box.setValue(getattr(getattr(self.edges[key],side),wall+"_m_flow_norm"));box.blockSignals(False)
        self.table.resizeColumnsToContents()

    def apply_to(self,params):
        for key,edges in self.edges.items():setattr(params,key,deepcopy(edges))

    def _changed(self,key,side,wall,value):
        setattr(getattr(self.edges[key],side),wall+"_m_flow_norm",value);self.parametersChanged.emit()

    def move_endpoint(self,key,side,wall,value):
        # Drag projection retains full float64 precision; formatting is UI only.
        self._changed(key,side,wall,value)
        box=self.controls[key,side,wall];box.blockSignals(True);box.setValue(value);box.blockSignals(False)
