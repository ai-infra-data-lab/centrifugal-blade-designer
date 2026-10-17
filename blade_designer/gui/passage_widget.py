"""Explicit, read-only analysis of the selected row's current master geometry."""
import numpy as np
import pyqtgraph as pg
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget,
                              QTableWidgetItem, QAbstractItemView, QTabWidget)
from ..geometry.passage import calculate_passages
from .plot_widgets import configure_plot

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="passage-analysis")


class PassageWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.source = None
        self._source_name = ''
        self.result = None
        self._generation = 0
        self._future = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(50)
        self._poll_timer.timeout.connect(self._poll)
        layout = QVBoxLayout(self)
        self.heading = QLabel("翼列を選択してください / Select a blade row")
        self.heading.setWordWrap(True)
        layout.addWidget(self.heading)
        self.calculate_button = QPushButton("流路面積・スロートを計算 / Calculate")
        self.calculate_button.clicked.connect(self.calculate)
        self.calculate_button.setEnabled(False)
        layout.addWidget(self.calculate_button)
        note = QLabel("面積: 子午面直交断面の周方向開口をSpan積分 [mm²]。"
                      "スロート: 各Spanの翼間最小幅 [mm] とHub–Tip積分の近似 [mm²]。\n"
                      "直線・円錐壁は展開計算、曲線壁は3D直線距離の下限推定です。\n"
                      "Netは指定したTip隙間の幾何開口を含み、両側通路とは別に表示します。"
                      "粘性・漏れ流量・境界層・根元フィレットは計算しません。"
                      "Main–Mainはスプリッター付きでは参考値です。")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.plot = pg.PlotWidget(background="#101c2b")
        configure_plot(self.plot, "Normalized Flow Meridional", "Area per main pitch [mm²]")
        self.plot.getAxis("bottom").enableAutoSIPrefix(False)
        self.plot.addLegend()
        self.curves = [self.plot.plot(pen=pg.mkPen(color, width=2), name=name, connect="finite")
                       for color, name in (("#899aa9", "Gross / N"), ("#56d9e0", "Main–Main reference"),
                                           ("#ffe477", "Net / main pitch"), ("#8deb87", "Main–Splitter"),
                                           ("#f28ac0", "Splitter–Main"), ("#bf9eff", "Tip-gap / N"))]
        self.plot.setMinimumHeight(180)
        layout.addWidget(self.plot)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.throat_table = QTableWidget(0, 6)
        self.throat_table.setHorizontalHeaderLabels(
            ["Passage", "Min width [mm]", "Span at min", "Throat area ≈ [mm²]", "N × area ≈ [mm²]", "Status"])
        layout.addWidget(self.throat_table)
        self.span_table = QTableWidget(0, 3)
        self.span_table.setHorizontalHeaderLabels(["Passage", "Span", "Throat width [mm]"])
        self.area_table = QTableWidget(0, 8)
        self.area_table.setHorizontalHeaderLabels(["m_flow", "Gross annulus [mm²]", "Net annulus [mm²]",
            "Main–Main ref [mm²]", "Net / main pitch [mm²]", "Main–Splitter [mm²]", "Splitter–Main [mm²]", "Tip-gap / N [mm²]"])
        self.details = QTabWidget()
        self.details.addTab(self.area_table, "断面面積 / Area stations")
        self.details.addTab(self.span_table, "Span別スロート / Throat by Span")
        layout.addWidget(self.details)
        for table in (self.throat_table, self.span_table, self.area_table):
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setStretchLastSection(True)
        self.errors = QLabel()
        self.errors.setWordWrap(True)
        layout.addWidget(self.errors)

    def set_source(self, geometry=None, vane_count=0, sign=1, name="", points=101, mean_points=4001):
        self._generation += 1
        self._source_name = name
        self.source = None if geometry is None else (geometry, vane_count, sign, points, mean_points)
        self.result = None
        self.heading.setText(f"対象: {name} — 未計算 / Calculate to refresh" if geometry is not None
                             else "翼列を選択してください。無効な現在値では計算できません。")
        self.calculate_button.setEnabled(self.source is not None and self._future is None)
        for curve in self.curves:
            curve.setData([], [])
        self.throat_table.setRowCount(0)
        self.span_table.setRowCount(0)
        self.area_table.setRowCount(0)
        self.summary.clear()
        self.errors.clear()

    def calculate(self):
        if self.source is None or self._future is not None:
            return
        self._running_source = deepcopy(self.source)
        self._running_generation = self._generation
        geometry, count, sign, points, mean_points = self._running_source
        self.result = None
        self.calculate_button.setEnabled(False)
        self.summary.setText("計算中 / Calculating…")
        self._future = _executor.submit(calculate_passages, geometry, count, sign, points=points, mean_points=mean_points)
        self._poll_timer.start()

    def _poll(self):
        if self._future is None or not self._future.done():
            return
        self._poll_timer.stop()
        future, self._future = self._future, None
        if self._generation != self._running_generation:
            self.calculate_button.setEnabled(self.source is not None)
            return  # A late result must never replace an edited or selected row.
        _, count, _, points, _ = self._running_source
        try:
            result = future.result()
            self.result = result
            self.heading.setText(f"対象: {self._source_name} — 計算済み / Calculated")
            x = [s.m_flow_norm for s in result.stations]
            # Never bridge missing samples or the upstream region without a full
            # splitter: NaN separators distinguish unavailable data from zero.
            for curve, name in zip(self.curves, ("gross_annulus", "main_reference", "net_per_pitch", "main_splitter", "splitter_main", "tip_gap_per_pitch")):
                values = [getattr(s, name) for s in result.stations]
                y = np.array([np.nan if v is None else v/count if name == "gross_annulus" else v for v in values])
                px, py = [], []
                for i, (position, value) in enumerate(zip(x, y)):
                    if i and position-x[i-1] > 1.51/(points-1):
                        px.append(np.nan); py.append(np.nan)
                    px.append(position); py.append(value)
                curve.setData(px, py, connect="finite")
            if result.stations:
                minimum = min(result.stations, key=lambda s: s.net_per_pitch)
                self.summary.setText(f"最小の子午面直交開口（サンプル値）: {minimum.net_per_pitch:.8g} mm² / main pitch"
                                     f"、全周 {minimum.net_per_pitch*count:.8g} mm²、m_flow={minimum.m_flow_norm:.6g}。"
                                     "スロート面積とは断面方向が異なります。")
            self.area_table.setRowCount(len(result.stations))
            for row, station in enumerate(result.stations):
                values = (station.m_flow_norm, station.gross_annulus, station.net_per_pitch*count,
                          station.main_reference, station.net_per_pitch, station.main_splitter, station.splitter_main, station.tip_gap_per_pitch)
                for col, value in enumerate(values):
                    self.area_table.setItem(row, col, QTableWidgetItem("N/A" if value is None else f"{value:.9g}"))
            self.throat_table.setRowCount(len(result.throats))
            self.span_table.setRowCount(sum(len(t.spans) for t in result.throats))
            span_row = 0
            for row, throat in enumerate(result.throats):
                values = (throat.name, f"{throat.minimum_width:.8g}",
                          f"{throat.spans[np.argmin(throat.widths)]:.6g}", f"{throat.strip_area:.8g}",
                          f"{throat.strip_area*count:.8g}", "Reference (ignores splitter)" if throat.reference_only else throat.method)
                for col, value in enumerate(values):
                    self.throat_table.setItem(row, col, QTableWidgetItem(value))
                self.throat_table.item(row, 5).setToolTip(throat.method+
                    '\nCurved wall: 3D直線距離の下限推定。壁面拘束付きの厳密なスロートではありません。'
                    if 'Curved wall' in throat.method else throat.method)
                for span, width in zip(throat.spans, throat.widths):
                    for col, value in enumerate((throat.name, f"{span:.6g}", f"{width:.8g}")):
                        self.span_table.setItem(span_row, col, QTableWidgetItem(value))
                    span_row += 1
            for table in (self.throat_table, self.span_table, self.area_table):
                table.resizeColumnsToContents()
            self.errors.setText("\n".join(result.errors[:3]))
            self.errors.setToolTip("\n".join(result.errors))
            self.plot.autoRange()
        except Exception as exc:
            # The source is read-only; no file is created and no previous numeric
            # result is left labelled as the current result.
            self.set_source(*self.source[:3], name="再確認が必要", points=points, mean_points=self.source[4])
            self.errors.setText(f"{type(exc).__name__}: {exc}")
        finally:
            self.calculate_button.setEnabled(self.source is not None)
