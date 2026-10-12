import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from blade_designer.gui.control_point_editor import ControlPointEditor
from blade_designer.gui.profile_distribution_editor import ProfileDistributionEditor
from blade_designer.models.parameters import DistributionPoint


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("kind", ["blade_angle", "thickness"])
def test_profile_rebuild_keeps_one_graph_and_removes_old_items(app, kind):
    editor = ProfileDistributionEditor(kind)
    points = [DistributionPoint(0, 1), DistributionPoint(.5, 2), DistributionPoint(1, 1)]
    plot = editor.plot
    try:
        # Check before deferred Qt deletion as well: no throwaway PlotWidgets.
        assert editor.findChildren(pg.PlotWidget) == [plot]
        for profiles in (
            [(0., "Hub", points), (1., "Tip", points)],
            [(0., "Hub", points), (.5, "Span .5", points), (1., "Tip", points)],
            [(0., "Diffuser", points)],
        ):
            old_items = [(e.curve, e.handles) for e in editor.series.values()]
            editor.set_profiles(profiles)
            assert editor.plot is plot
            assert editor.findChildren(pg.PlotWidget) == [plot]
            for curve, handles in old_items:
                assert curve not in plot.items() and handles not in plot.items()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
            assert plot.parentWidget() is editor
            assert len(plot.listDataItems()) == len(profiles)
            editor.series[0.].move_point(1, .4, 3)
            assert editor.series[0.].get_points()[1] == DistributionPoint(.4, 3)
            for span, _, _ in profiles:
                editor.update_profile_distribution(span, np.array([0., 1.]), np.array([1., 2.]))
                np.testing.assert_array_equal(editor.series[span].curve.yData, [1., 2.])
            assert all(e.plot is plot for e in editor.series.values())
    finally:
        editor.close(); editor.deleteLater(); app.processEvents()


@pytest.mark.parametrize("kind", ["blade_angle", "thickness"])
def test_standalone_control_editor_still_owns_graph_and_input(app, kind):
    editor = ControlPointEditor(kind)
    try:
        assert editor.plot.parentWidget() is editor
        assert editor.findChildren(pg.PlotWidget) == [editor.plot]
        editor.set_points([DistributionPoint(0, 1), DistributionPoint(.5, 2), DistributionPoint(1, 1)])
        editor.table.cellWidget(1, 1).setValue(3)
        assert editor.get_points()[1].value == 3
        editor.add_point()
        assert len(editor.get_points()) == 4
        editor.delete_point()
        assert len(editor.get_points()) == 3
    finally:
        editor.close(); editor.deleteLater(); app.processEvents()
