import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import EdgeType
from blade_designer.fileio.project_io import load_project
from test_tangent_arcs import join_cosines


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    p=load_project(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json')
    w=MainWindow(default_parameters=p);w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


@pytest.mark.parametrize('identifier',['row-1','row-2','row-3'])
def test_regular_rounding_is_tangent_on_load_and_ellipse_edit_matches_2d_3d_history(window,identifier,tmp_path):
    w=window;w.select_blade_row(identifier);w.annulus_2d.setChecked(False);w.update_geometry()
    before=deepcopy(w.get_parameters())
    # The bundled Impeller TE is a deliberate cylindrical Cutoff, not rounding.
    assert min(join_cosines(w._selected_3d_geometry.sections[0])[:2])>1-2e-8
    combo=w.panel.controls['le_type'];combo.setCurrentIndex(combo.findData(EdgeType.ELLIPTICAL));w.update_geometry()
    after=deepcopy(w.get_parameters());assert after!=before
    assert w.panel.controls['le_ellipse_ratio'].isEnabled()
    w.undo();w.update_geometry();assert w.get_parameters()==before
    w.redo();w.update_geometry();assert w.get_parameters()==after
    w.panel.controls['le_ellipse_ratio'].setValue(2);w.update_geometry()
    section=w._selected_3d_geometry.sections[0]
    assert min(join_cosines(section)[:2])>1-2e-8
    for role in ('le','ps','te','ss'):
        x,y=w.blade_plot.curves[role.upper()].getData();curve=getattr(section,'master_'+role)
        np.testing.assert_array_equal(x,curve.x);np.testing.assert_array_equal(y,curve.y)
    final=deepcopy(w.get_parameters());path=tmp_path/'ellipse.json';w.save_to_path(path)
    w.load_from_path(path);w.update_geometry();assert w.get_parameters()==final
