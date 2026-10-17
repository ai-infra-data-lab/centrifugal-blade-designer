from copy import deepcopy
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QDoubleSpinBox, QPushButton, QLabel, QAbstractItemView)
from ..models.parameters import DistributionPoint
from ..models.validation import validate_control_points, ValidationLevel
from .plot_fitting import install_plot_fit


class CompactDoubleSpinBox(QDoubleSpinBox):
    def textFromValue(self, value: float) -> str:
        text = super().textFromValue(value)
        separator = self.locale().decimalPoint()
        return text.rstrip("0").rstrip(separator) if separator in text else text


class DraggablePoints(pg.GraphItem):
    def __init__(self, editor: "ControlPointEditor") -> None:
        super().__init__()
        self.editor = editor
        self.drag_index: int | None = None
        self.scatter.sigClicked.connect(self._clicked)

    def _clicked(self, scatter: object, points: list, event: object) -> None:
        if len(points):
            self.editor.table.selectRow(int(points[0].data()))

    def set_points(self, points: list[DistributionPoint]) -> None:
        data = np.arange(len(points))
        self.setData(pos=np.array([[p.m_blade_norm,p.value] for p in points]).reshape(-1,2), data=data,
                     size=getattr(self,"point_size",12), symbol=getattr(self,'symbol','o'),
                     symbolPen=pg.mkPen(getattr(self,"color","#56d9e0"),width=2),
                     symbolBrush=getattr(self,"brush","#56d9e0"), pxMode=True)

    def hoverEvent(self, event: object) -> None:
        # Claim point drags before ViewBox pan handling, independent of widget size.
        if not event.isExit() and len(self.scatter.pointsAt(event.pos())) > 0:
            event.acceptDrags(Qt.MouseButton.LeftButton)
            event.acceptClicks(Qt.MouseButton.LeftButton)

    def mouseClickEvent(self, event: object) -> None:
        points = self.scatter.pointsAt(event.pos())
        if event.button() == Qt.MouseButton.LeftButton and points:
            self.editor.table.selectRow(int(points[0].data()))
            event.accept()
        else:
            event.ignore()

    def mouseDragEvent(self, event: object) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        if event.isStart():
            points = self.scatter.pointsAt(event.buttonDownPos())
            if len(points) == 0:
                event.ignore()
                return
            self.editor.dragStarted.emit()
            self.drag_index = int(points[0].data())
            self.editor.plot.disableAutoRange()
            self.editor.table.selectRow(self.drag_index)
        if self.drag_index is None:
            event.ignore()
            return
        position = event.pos()
        self.editor.move_point(self.drag_index, position.x(), position.y())
        if event.isFinish():
            self.drag_index = None
            self.editor.dragFinished.emit()
        event.accept()


class ControlPointEditor(QWidget):
    pointsChanged = Signal()
    dragStarted = Signal()
    dragFinished = Signal()
    editFinished = Signal()

    def __init__(self, kind: str, parent: QWidget | None = None, *, shared_plot: pg.PlotWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._points: list[DistributionPoint] = []
        layout = QVBoxLayout(self)
        self.plot = shared_plot if shared_plot is not None else pg.PlotWidget(background="#101c2b")
        install_plot_fit(self.plot)
        if shared_plot is None:
            self.plot.setMinimumHeight(180)
            self.plot.setLabel("bottom", "Normalized Meridional")
            self.plot.getAxis("bottom").setHeight(48)
            self.plot.getAxis("left").setWidth(80)
            self.plot.setLabel("left", "Blade Angle βm [deg]" if kind == "blade_angle" else "Thickness [mm]")
            self.plot.showGrid(x=True,y=True,alpha=.2)
            for name in ("bottom","left"):
                self.plot.getAxis(name).setTextPen("#d1dae7")
        self.curve = self.plot.plot(pen=pg.mkPen("#e5c76b",width=2))
        self.handles = DraggablePoints(self)
        self.plot.addItem(self.handles)
        if shared_plot is None:
            layout.addWidget(self.plot,1)
            layout.addWidget(QLabel("Drag a point or edit the table. Endpoints remain at 0 and 1."))
        self.table = QTableWidget(0,2)
        self.table.setHorizontalHeaderLabels(["Normalized Meridional","βm [deg]" if kind == "blade_angle" else "Thickness [mm]"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0,220)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMaximumHeight(200)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.add_button = QPushButton("Add Point")
        self.delete_button = QPushButton("Delete Point")
        self.add_button.clicked.connect(self.add_point)
        self.delete_button.clicked.connect(self.delete_point)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        actions.addWidget(self.add_button)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

    def get_points(self) -> list[DistributionPoint]:
        return deepcopy(self._points)

    def set_points(self, points: list[DistributionPoint]) -> None:
        self._points = deepcopy(points)
        self.table.setRowCount(len(points))
        for i,p in enumerate(points):
            for col,value in enumerate((p.m_blade_norm,p.value)):
                box = CompactDoubleSpinBox()
                box.setDecimals(12)
                box.setRange(0.,1.) if col == 0 else box.setRange(-1e12,1e12)
                box.setSingleStep(.01 if col == 0 else .1)
                box.setValue(value)
                box.setEnabled(col != 0 or i not in (0,len(points)-1))
                box.valueChanged.connect(lambda val, row=i, column=col: self._cell_changed(row,column,val))
                box.editingFinished.connect(self.editFinished)
                self.table.setCellWidget(i,col,box)
        self.handles.set_points(points)
        self._selection_changed()
        self._show_validation()

    def _cell_changed(self, row: int, column: int, value: float) -> None:
        setattr(self._points[row],"m_blade_norm" if column == 0 else "value",value)
        self.handles.set_points(self._points)
        self._show_validation()
        self.pointsChanged.emit()

    def _show_validation(self) -> None:
        errors = [i.message for i in validate_control_points(self._points,self.kind) if i.level == ValidationLevel.ERROR]
        self.message.setText("; ".join(errors))
        self.message.setStyleSheet("color: #b03030;")

    def _selection_changed(self) -> None:
        row = self.table.currentRow()
        self.delete_button.setEnabled(0 < row < len(self._points)-1)

    def add_point(self) -> None:
        if len(self._points) < 2:
            return
        errors = validate_control_points(self._points,self.kind)
        if any(i.level == ValidationLevel.ERROR for i in errors):
            self.message.setText("Correct invalid control points before adding a point.")
            return
        i = int(np.argmax(np.diff([p.m_blade_norm for p in self._points])))
        a,b = self._points[i:i+2]
        points = self.get_points()
        points.insert(i+1,DistributionPoint((a.m_blade_norm+b.m_blade_norm)/2,(a.value+b.value)/2))
        self.set_points(points)
        self.table.selectRow(i+1)
        self.pointsChanged.emit()
        self.editFinished.emit()

    def delete_point(self) -> None:
        i = self.table.currentRow()
        if not 0 < i < len(self._points)-1:
            return
        points = self.get_points()
        del points[i]
        self.set_points(points)
        self.pointsChanged.emit()
        self.editFinished.emit()

    def move_point(self, index: int, m_blade_norm: float, value: float) -> None:
        points = self._points
        if index == 0:
            m_blade_norm = 0.
        elif index == len(points)-1:
            m_blade_norm = 1.
        else:
            lo, hi = points[index-1].m_blade_norm, points[index+1].m_blade_norm
            margin = min(1e-6,(hi-lo)/4)
            m_blade_norm = float(np.clip(m_blade_norm,lo+margin,hi-margin))
        value = float(np.clip(value,-84.999999,84.999999)) if self.kind == "blade_angle" else max(0.,float(value))
        points[index] = DistributionPoint(m_blade_norm,value)
        for col,v in enumerate((m_blade_norm,value)):
            box = self.table.cellWidget(index,col)
            box.blockSignals(True)
            box.setValue(v)
            box.blockSignals(False)
        self.handles.set_points(points)
        self._show_validation()
        self.pointsChanged.emit()

    def update_distribution(self, m_blade_norm: np.ndarray, values: np.ndarray) -> None:
        self.curve.setData(m_blade_norm,values)
        if self.handles.drag_index is None:
            self.plot.disableAutoRange()
