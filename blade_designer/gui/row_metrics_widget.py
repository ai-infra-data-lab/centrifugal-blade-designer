"""Measurements of the same sampled sections used by the central model view."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QPushButton, QSizePolicy
from ..geometry.section_measurements import measure_section
from .plot_widgets import configure_plot
from .plot_fitting import install_plot_fit


class RowMetricsWidget(QWidget):
    refreshRequested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.identity = QLabel()
        self.identity.setWordWrap(True)
        self.identity.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.identity)
        self.refresh_button = QPushButton('形状・指標を再計算 / Refresh')
        self.refresh_button.clicked.connect(self.refreshRequested)
        layout.addWidget(self.refresh_button)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Actual section metric', 'Value'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 320)
        self.table.setMinimumHeight(100)
        self.table.setMaximumHeight(190)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        layout.addWidget(self.table, 2)
        self.section_choice = QComboBox()
        self.section_choice.currentIndexChanged.connect(self._measure)
        layout.addWidget(self.section_choice)
        self.choice = QComboBox()
        self.choice.addItems(['Pitch', 'Camber chord / Pitch', 'PS |curvature| XYZ', 'SS |curvature| XYZ'])
        self.choice.currentIndexChanged.connect(self._plot)
        layout.addWidget(self.choice)
        self.plot = pg.PlotWidget(background='#101c2b')
        self.plot.setMinimumSize(160, 140)
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        configure_plot(self.plot, 'Blade streamwise coordinate', 'Pitch [mm]')
        self.curve = self.plot.plot(pen=pg.mkPen('#56d9e0', width=2))
        layout.addWidget(self.plot, 3)
        note = QLabel('XYZ chord: camber endpoints. Length: sampled XYZ polyline. Curvature: nonnegative spatial spline curvature.\n'
                      'Throat / flow blockage: use Passage Area / Throat. These section metrics do not prove 3D interference freedom.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.geometry = self.source = self.measurements = None
        self.invalidate()

    def invalidate(self, message='設計・編集対象が変わりました。形状を再計算してください。'):
        self.geometry = self.source = self.measurements = None
        self.identity.setText(message)
        self.identity.setToolTip('')
        self.table.setRowCount(0)
        self.curve.setData([], [])
        self.section_choice.setEnabled(False)
        self.choice.setEnabled(False)

    def update_geometry(self, geometry, source, blade_count):
        previous = self.section_choice.currentData()
        self.geometry, self.source, self.blade_count = geometry, source, blade_count
        self.section_choice.setEnabled(True)
        self.choice.setEnabled(True)
        self.section_choice.blockSignals(True)
        self.section_choice.clear()
        self.sections = []
        for name, sections in (('Main', geometry.sections), ('Splitter', geometry.splitter_sections)):
            for section in sections or []:
                key = f'{name}:{section.span:.15g}'
                self.section_choice.addItem(f'{name} / Span {section.span:g}', key)
                self.sections.append(section)
        index = self.section_choice.findData(previous)
        self.section_choice.setCurrentIndex(max(0, index))
        self.section_choice.blockSignals(False)
        self._measure()

    def _measure(self):
        if self.geometry is None:
            return
        self.identity.setToolTip('Snapshot: '+self.source.snapshot_hash)
        try:
            self.measurements = measure_section(self.sections[self.section_choice.currentIndex()], self.blade_count)
        except (ValueError, ArithmeticError) as exc:
            self.measurements = None
            self.identity.setText(self.source.label+'\n測定不可: '+str(exc))
            self.table.setRowCount(0)
            self.curve.setData([], [])
            return
        self.identity.setText(self.source.label)
        m = self.measurements
        rows = [('Blade Count', self.blade_count), ('Camber LE R [mm]', m.radii[0]), ('Camber TE R [mm]', m.radii[-1]),
                ('Camber LE Z [mm]', m.z[0]), ('Camber TE Z [mm]', m.z[-1]),
                ('Camber endpoint chord XYZ [mm]', m.camber_chord_xyz), ('Camber polyline length XYZ [mm]', m.camber_length_xyz),
                ('LE Pitch [mm]', m.pitch[0]), ('TE Pitch [mm]', m.pitch[-1]),
                ('Maximum PS |curvature| XYZ [1/mm]', np.max(m.ps_curvature_xyz)),
                ('Maximum SS |curvature| XYZ [1/mm]', np.max(m.ss_curvature_xyz))]
        self.table.setRowCount(len(rows))
        for i, (label, value) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(label))
            self.table.setItem(i, 1, QTableWidgetItem(f'{value:.12g}'))
        self._plot()

    def _plot(self):
        m = self.measurements
        if m is None:
            return
        x, y, label = [(m.streamwise, m.pitch, 'Pitch [mm]'),
                       (m.streamwise, m.camber_chord_xyz/m.pitch, 'Camber chord / Pitch'),
                       (m.ps_streamwise, m.ps_curvature_xyz, '|Curvature| XYZ [1/mm]'),
                       (m.ss_streamwise, m.ss_curvature_xyz, '|Curvature| XYZ [1/mm]')][self.choice.currentIndex()]
        self.curve.setData(x, y)
        self.plot.setLabel('left', label)
        install_plot_fit(self.plot).request()
