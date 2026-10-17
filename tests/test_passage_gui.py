"""Selected-row wiring, asynchronous snapshot isolation, stale result protection."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from concurrent.futures import Future
from copy import deepcopy
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from blade_designer.gui.main_window import MainWindow
from blade_designer.gui.passage_widget import PassageWidget
from blade_designer.geometry.passage import calculate_passages
from blade_designer.models.parameters import SplitterParameters
from test_passage import radial


def wait_result(widget, timeout=30):
    deadline = time.monotonic()+timeout
    while widget._future is not None and time.monotonic() < deadline:
        QTest.qWait(20)
    assert widget._future is None


def test_async_calculation_displays_both_splitter_passages_and_changes_clear_results():
    app = QApplication.instance() or QApplication([])
    widget = PassageWidget()
    try:
        geometry = radial(True)
        widget.set_source(geometry, 12, 1, 'Impeller', 51)
        widget.calculate()
        assert not widget.calculate_button.isEnabled()
        wait_result(widget)
        assert widget.result is not None and not widget.result.errors
        assert 'Calculated' in widget.heading.text()
        assert widget.throat_table.rowCount() == 3 and widget.span_table.rowCount() == 9
        assert widget.throat_table.item(0, 5).text() == 'Reference (ignores splitter)'
        assert widget.throat_table.item(1, 0).text() == 'Main–Splitter'
        assert widget.throat_table.item(2, 0).text() == 'Splitter–Main'
        assert '全周' in widget.summary.text()
        assert widget.curves[3].xData is not None
        assert widget.area_table.rowCount() == len(widget.result.stations)
        assert any(widget.area_table.item(row, 5).text() == 'N/A' for row in range(widget.area_table.rowCount()))
        widget.set_source(geometry, 14, 1, 'Changed')
        assert widget.result is None and widget.throat_table.rowCount() == 0
        assert widget.curves[3].xData is None or len(widget.curves[3].xData) == 0
    finally:
        widget.close(); widget.deleteLater(); app.processEvents()


def test_late_results_and_failed_analysis_do_not_replace_current_source(monkeypatch):
    import blade_designer.gui.passage_widget as module
    app = QApplication.instance() or QApplication([])
    widget = PassageWidget()
    pending = Future()
    captured = []
    class Executor:
        def submit(self, function, *args, **kwargs):
            captured.append(args)
            return pending
    monkeypatch.setattr(module, '_executor', Executor())
    try:
        row = radial()
        widget.set_source(row, 12, 1, 'Old')
        widget.calculate()
        assert captured[0][0] is not row
        widget.set_source(row, 14, 1, 'New')
        pending.set_result(calculate_passages(row, 12, points=21))
        widget._poll()
        assert widget.result is None and 'New' in widget.heading.text()
        assert widget.calculate_button.isEnabled()
        pending = Future()
        widget.calculate()
        pending.set_exception(ValueError('Invalid passage'))
        widget._poll()
        assert widget.result is None and widget.throat_table.rowCount() == 0
        assert 'Invalid passage' in widget.errors.text()
    finally:
        widget.close(); widget.deleteLater(); app.processEvents()


def test_main_window_uses_selected_actual_3d_row_and_clears_on_invalid_input(monkeypatch):
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        action = next(a for a in w.view_menu.actions() if a.text() == 'Passage Area / Throat')
        action.trigger()
        assert w._tool_dialogs['Passage Area / Throat'].isVisible()
        assert w.passage_widget.source[0] is w.impeller_geometry
        w.select_blade_row('row-2')
        assert w.passage_widget.source[0] is w._selected_3d_geometry
        assert w.passage_widget.source[0] is not w.impeller_geometry
        assert w.passage_widget.source[0].splitter_sections is None
        w._select_meridional()
        assert w.passage_widget.source is None
        # Re-selecting the same row must restore the analysis source too.
        w.select_blade_row('row-2')
        assert w.passage_widget.source is not None
        p = deepcopy(w.get_parameters())
        w._schedule_update()
        assert w.passage_widget.source is None
        w.update_geometry()
        assert w.passage_widget.source is not None
        assert w.get_parameters() == p
        w.select_blade_row('row-1')
        p = w.get_parameters(); p.splitter = SplitterParameters()
        w.set_parameters(p); w.update_geometry()
        assert w.passage_widget.source[0].splitter_sections
        assert w.passage_widget.source[1] == p.geometry.vane_count
        w.panel.controls['vane_count'].setValue(1)
        w.update_geometry()
        w.passage_widget.calculate()
        wait_result(w.passage_widget)
        assert w.passage_widget.result is None
        assert 'at least two' in w.passage_widget.errors.text()
        def invalid_current(_):
            raise ValueError('Invalid current geometry')
        monkeypatch.setattr(w.designer, 'generate_3d', invalid_current)
        w.update_geometry()
        assert w.passage_widget.source is None
        w.select_blade_row('row-1')
        assert w.passage_widget.source is None
        assert not w.passage_widget.calculate_button.isEnabled()
    finally:
        for dialog in w._tool_dialogs.values(): dialog.close()
        w.timer.stop(); w.close(); w.deleteLater(); app.processEvents()
