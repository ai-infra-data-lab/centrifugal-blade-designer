"""Shared distribution graph with directly editable controls for every section."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea
import pyqtgraph as pg
from .control_point_editor import ControlPointEditor


class ProfileDistributionEditor(QWidget):
    pointsChanged = Signal()
    dragStarted = Signal()
    dragFinished = Signal()
    editFinished = Signal()

    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.series = {}
        self.active_span = 0.0
        self.layout_main = QVBoxLayout(self)
        self.plot = pg.PlotWidget(background="#101c2b")
        self.plot.setMinimumHeight(180)
        self.plot.setLabel("bottom", "Normalized Meridional")
        self.plot.setLabel("left", "Blade Angle βm [deg]" if kind == "blade_angle" else "Thickness [mm]")
        self.plot.getAxis("left").setWidth(80)
        self.plot.getAxis("bottom").setHeight(48)
        self.plot.showGrid(x=True, y=True, alpha=.2)
        for name in ("bottom", "left"):
            self.plot.getAxis(name).setTextPen("#d1dae7")
        self.legend = self.plot.addLegend()
        self.layout_main.addWidget(self.plot, 1)
        self.hint = QLabel("Hub: cyan center • Tip: orange outer ring. Drag either point or edit either table.")
        self.hint.setWordWrap(True)
        self.layout_main.addWidget(self.hint)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(230)
        self.layout_main.addWidget(self.scroll)
        self.set_profiles([(0.0, "Hub", [])])

    def set_profiles(self, profiles, active_span=0.0):
        keys = [span for span, _, _ in profiles]
        if list(self.series) != keys:
            for editor in self.series.values():
                self.plot.removeItem(editor.curve)
                self.plot.removeItem(editor.handles)
            self.legend.clear()
            old = self.scroll.takeWidget()
            if old is not None:
                old.deleteLater()
            container = QWidget()
            tables = QHBoxLayout(container)
            self.series = {}
            colors = ["#56d9e0", "#c7a6ff", "#7fd28b", "#f192bc"]
            for index, (span, name, _) in enumerate(profiles):
                editor = ControlPointEditor(self.kind, shared_plot=self.plot)
                color = "#ffad55" if span == 1.0 else colors[index % len(colors)]
                editor.curve.setPen(pg.mkPen(color, width=3 if span == 1 else 2,
                    style=Qt.PenStyle.DashLine if span == 1 else Qt.PenStyle.SolidLine))
                editor.handles.color = color
                editor.handles.point_size = 24 if span == 1 else 12
                editor.handles.brush = None if span == 1 else color
                editor.handles.setZValue(10 if span == 0 else 5)
                self.legend.addItem(editor.curve, name)
                label = QLabel(name)
                label.setStyleSheet(f"color: {color}; font-weight: bold; background: #101c2b; padding: 4px;")
                editor.layout().insertWidget(0, label)
                editor.table.setMinimumHeight(155)
                editor.table.setColumnWidth(0, 115)
                editor.table.setHorizontalHeaderLabels(["M norm", "βm [deg]" if self.kind == "blade_angle" else "Thickness [mm]"])
                editor.setMinimumWidth(220)
                for signal in ("pointsChanged", "dragStarted", "dragFinished", "editFinished"):
                    getattr(editor, signal).connect(getattr(self, signal).emit)
                tables.addWidget(editor)
                self.series[span] = editor
            self.scroll.setWidget(container)
        self.active_span = active_span if active_span in self.series else keys[0]
        for span, _, points in profiles:
            self.series[span].set_points(points)
        self.hint.setText("Hub: cyan center • Tip: orange outer ring. Drag either point or edit either table."
                          if len(profiles) > 1 else "Diffuser: drag a point or edit the table.")

    def update_profile_distribution(self, span, positions, values):
        self.series[span].update_distribution(positions, values)

    # Keep the legacy single-section API for integrations and LE/TE selection.
    # All other tables and graphic items remain visible and directly editable.
    def __getattr__(self, name):
        if name in ("table", "handles", "curve", "add_button", "delete_button", "message",
                    "get_points", "set_points", "move_point", "add_point", "delete_point", "update_distribution"):
            return getattr(self.series[self.active_span], name)
        raise AttributeError(name)
