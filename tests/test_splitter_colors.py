"""Offscreen display contracts; no geometry or export changes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from copy import deepcopy
import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from blade_designer.gui.plot_widgets import BladePlotWidget, FullAnnulusPlotWidget
from blade_designer.gui.preview_3d import Preview3D
from blade_designer.geometry.annulus import project_annulus
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.models.parameters import SplitterParameters
from test_impeller_te_rake import radial_parameters


PALETTE = {'LE': '#e5c76b', 'PS': '#56d9e0', 'TE': '#eead72', 'SS': '#f6948c'}


@pytest.fixture(scope='module')
def geometry():
    p = radial_parameters()
    p.splitter = SplitterParameters()
    return generate_impeller(p)


@pytest.mark.parametrize('widget_type', [BladePlotWidget, FullAnnulusPlotWidget])
@pytest.mark.parametrize('projection', ['XY', 'XZ', 'YZ'])
@pytest.mark.parametrize('count', [1, 7])
def test_splitter_role_colors_legend_style_and_coordinates(geometry, widget_type, projection, count):
    app = QApplication.instance() or QApplication([])
    widget = widget_type()
    section = geometry.splitter_sections[0]
    before = section.master_ps.xyz.copy()
    try:
        widget.update_splitter(section, projection, count)
        labels = {label.text for _, label in widget.plotItem.legend.items}
        for role, color in PALETTE.items():
            curve = widget.splitter_curves[role]
            assert curve.opts['pen'].color().name() == color
            main_pen = pg.mkPen(widget.curves[role].opts['pen'])
            assert main_pen.color().name() == color
            assert curve.opts['pen'].style() == Qt.PenStyle.DashLine
            assert main_pen.style() == Qt.PenStyle.SolidLine
            assert 'Splitter ' + role in labels
            segment = getattr(section, 'master_' + role.lower())
            expected = project_annulus(segment.x, segment.y, segment.z, count, projection)
            for actual, target in zip(curve.getData(), expected):
                np.testing.assert_array_equal(actual, target)
        widget.update_splitter(None, projection, count)
        for curve in widget.splitter_curves.values():
            assert curve.getData()[0] is None or len(curve.getData()[0]) == 0
        widget.update_splitter(section, projection, count)
        assert len(widget.splitter_curves) == 4
        np.testing.assert_array_equal(section.master_ps.xyz, before)
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('all_rows', [False, True])
@pytest.mark.parametrize('full_annulus', [False, True])
def test_3d_splitter_roles_preserve_camera_geometry_and_neutral_grid(geometry, all_rows, full_annulus):
    app = QApplication.instance() or QApplication([])
    preview = Preview3D()
    camera = deepcopy(preview.camera_position)
    before = geometry.splitter_sections[0].master_ps.xyz.copy()
    try:
        if all_rows:
            preview.update_rows([('row-1', 'Impeller', geometry, 7)], geometry)
        else:
            preview.update_geometry(geometry)
        preview.set_full_annulus(full_annulus, 7)
        prefix = 'Impeller [row-1] ' if all_rows else ''
        for section in geometry.splitter_sections:
            label = 'Hub' if section.span == 0 else 'Tip' if section.span == 1 else f'Span {section.span:.6g}'
            for role, color in PALETTE.items():
                key = prefix + 'Splitter ' + label + ' ' + role.lower()
                points, actual = preview.base_lines[key]
                assert actual == color == preview.base_lines[prefix + label + ' ' + role.lower()][1]
                np.testing.assert_array_equal(points, getattr(section, 'master_' + role.lower()).xyz)
                rendered = [value for name, value in preview.lines.items() if name == key or name.startswith(key + ' • blade ')]
                assert len(rendered) == (7 if full_annulus else 1)
                assert all(value[1] == color for value in rendered)
        for name, (_, color) in preview.base_lines.items():
            if name.startswith('Spanwise '):
                assert color == '#496b8e'
            elif name.endswith('camber'):
                assert color == '#aab4c5'
        for key, value in camera.items():
            np.testing.assert_array_equal(preview.camera_position[key], value)
        np.testing.assert_array_equal(geometry.splitter_sections[0].master_ps.xyz, before)
    finally:
        preview.close()
        preview.deleteLater()
        app.processEvents()
