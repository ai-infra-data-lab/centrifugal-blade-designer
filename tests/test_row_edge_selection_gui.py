"""Loaded meridional edge groups retain their values and actual row owners."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import hashlib
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.models.parameters import BladeParameters,BladeRow
from blade_designer.models.blade_rows import (initial_rows,row_snapshot,
    reconcile_visible_row_edges)
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.gui.main_window import MainWindow


def stale_project():
    p=BladeParameters();p.blade_rows=initial_rows(p);p.active_blade_row="row-1"
    # Reproduce the old GUI: editing DIF while IMP was selected only changed
    # the visible/top-level values and the IMP snapshot, leaving DIF stale.
    p.diffuser_edges.leading_edge.hub_m_flow_norm=.88
    p.blade_rows[0].parameters.diffuser_edges=deepcopy(p.diffuser_edges)
    return p


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


@pytest.mark.parametrize("active",["row-1","row-3"])
def test_loaded_edge_reconciliation_preserves_other_independent_rows(active):
    p=stale_project()
    other=row_snapshot(p);other.diffuser_edges.leading_edge.hub_m_flow_norm=.92
    p.blade_rows.append(BladeRow("row-3","Second diffuser","diffuser",other))
    p.active_blade_row=active;before=deepcopy(p)
    result=reconcile_visible_row_edges(p)
    target=1 if active=="row-1" else 2
    assert result.blade_rows[target].parameters.diffuser_edges==p.diffuser_edges
    assert result.blade_rows[3-target].parameters.diffuser_edges==p.blade_rows[3-target].parameters.diffuser_edges
    assert p==before


def displayed_coordinates(w):
    return {key:box.value() for key,box in w.meridional_editor.blade_edges.coordinate_controls.items()}


def test_load_and_select_diffuser_keeps_visible_le_te_and_source(window,tmp_path):
    w=window;p=stale_project();path=tmp_path/"stale-edges.json";save_project(path,p)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    w.load_from_path(path);before=w.get_parameters();coordinates=displayed_coordinates(w)
    assert before.impeller_edges==p.impeller_edges and before.diffuser_edges==p.diffuser_edges
    for identifier in ("row-2","row-1","row-2"):
        w.select_blade_row(identifier);w.update_geometry();after=w.get_parameters()
        assert after.impeller_edges==before.impeller_edges and after.diffuser_edges==before.diffuser_edges
        assert displayed_coordinates(w)==coordinates
        assert w.undo_stack.count()==0
    assert [s.span for s in w.diffuser_geometry.sections]==[0,1]
    for line in w.model_preview_3d.spanwise_lines:
        assert line.xyz.shape==(2,3);np.testing.assert_array_equal(line.spans,[0,1])
    assert "Span 0.5 camber" not in w.model_preview_3d.base_lines
    saved=tmp_path/"corrected.json";w.save_to_path(saved);w.load_from_path(saved)
    assert w.get_parameters().diffuser_edges==p.diffuser_edges
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest


def test_edit_diffuser_edges_from_impeller_is_saved_to_diffuser_and_undo(window,tmp_path):
    w=window;w.select_blade_row("row-1");before=deepcopy(w.get_parameters())
    count=w.undo_stack.count()
    box=w.meridional_editor.blade_edges.controls["diffuser_edges","leading_edge","hub"]
    box.setValue(.89);box.editingFinished.emit();w.update_geometry()
    after=deepcopy(w.get_parameters())
    assert after.blade_rows[1].parameters.diffuser_edges.leading_edge.hub_m_flow_norm==.89
    assert after.blade_rows[0].parameters.impeller_edges==before.blade_rows[0].parameters.impeller_edges
    assert w.undo_stack.count()==count+1
    w.undo();assert w.get_parameters()==before
    w.redo();assert w.get_parameters()==after
    w.select_blade_row("row-2");assert w.get_parameters().diffuser_edges==after.diffuser_edges
    path=tmp_path/"row-edit.json";w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters().diffuser_edges==after.diffuser_edges


def test_multiple_diffusers_keep_independent_edges_and_other_group(window,tmp_path):
    w=window;w.select_blade_row("row-2");impeller=deepcopy(w.get_parameters().impeller_edges)
    w.add_blade_row("diffuser","Second diffuser");second=w.get_parameters().active_blade_row
    box=w.meridional_editor.blade_edges.controls["diffuser_edges","leading_edge","hub"]
    box.setValue(.92);box.editingFinished.emit()
    w.select_blade_row("row-1")
    assert w.get_parameters().diffuser_edges.leading_edge.hub_m_flow_norm==.9
    w.select_blade_row(second)
    assert w.get_parameters().diffuser_edges.leading_edge.hub_m_flow_norm==.92
    assert w.get_parameters().impeller_edges==impeller
    path=tmp_path/"two-diffusers.json";w.save_to_path(path);w.load_from_path(path)
    w.select_blade_row("row-2");assert w.get_parameters().diffuser_edges.leading_edge.hub_m_flow_norm==.9
    w.select_blade_row(second);assert w.get_parameters().diffuser_edges.leading_edge.hub_m_flow_norm==.92
