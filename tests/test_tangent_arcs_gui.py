"""Offscreen selection/history of the new edge type, without GUI redesign."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import BladeParameters,EdgeType
from blade_designer.fileio.project_io import load_project
from blade_designer.geometry.geometry_3d import generate_impeller


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow(default_parameters=BladeParameters());w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_choose_tangent_arc_shared_spans_undo_redo_and_save(window,tmp_path):
    w=window;before=deepcopy(w.get_parameters())
    combo=w.panel.controls['le_type'];assert combo.findData(EdgeType.TANGENT_CIRCULAR)>=0
    assert 'Tangent arc' in combo.itemText(combo.findData(EdgeType.TANGENT_CIRCULAR))
    combo.setCurrentIndex(combo.findData(EdgeType.TANGENT_CIRCULAR));w.update_geometry()
    after=deepcopy(w.get_parameters())
    assert all(s.edge_parameters.le_type==EdgeType.TANGENT_CIRCULAR for s in after.sections)
    assert not w.panel.controls['le_ellipse_ratio'].isEnabled()
    for a,b in zip(before.sections,after.sections):
        assert a.blade_angle==b.blade_angle and a.thickness==b.thickness
    expected=generate_impeller(after)
    np.testing.assert_array_equal(w.impeller_geometry.sections[0].master_le.xyz,expected.sections[0].master_le.xyz)
    w.undo();w.update_geometry();assert w.get_parameters()==before
    w.redo();w.update_geometry();assert w.get_parameters()==after
    path=tmp_path/'tangent.json';w.save_to_path(path)
    assert load_project(path)==after
    w.new_project();w.load_from_path(path);w.update_geometry()
    assert w.get_parameters()==after


def test_static_edge_option_stays_independent_of_impeller(window):
    w=window;original=deepcopy(w.get_parameters().sections)
    w.view_mode.setCurrentIndex(1)
    for side in ('le','te'):
        combo=w.panel.controls[side+'_type']
        combo.setCurrentIndex(combo.findData(EdgeType.TANGENT_CIRCULAR))
    w.update_geometry();p=w.get_parameters()
    assert p.sections==original
    assert p.diffuser_profile.edge_parameters.le_type==p.diffuser_profile.edge_parameters.te_type==EdgeType.TANGENT_CIRCULAR
    assert w.diffuser_geometry is not None
