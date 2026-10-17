import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import csv
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from main import create_window,parse_arguments
from blade_designer.fileio.geometry_source import geometry_source
from test_standard_menus_gui import dispose


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([]);w=create_window(parse_arguments([]));w.timer.stop()
    yield w
    dispose(w,app)


def test_rc_measurements_and_csv_use_displayed_inward_master_while_legacy_remains_explicit(window,tmp_path):
    w=window;params=deepcopy(w.get_parameters());history=w.undo_stack.count();camera=deepcopy(w.model_preview_3d.camera_position)
    widget=w.row_metrics_widget;g=w.diffuser_geometry
    assert widget.geometry is g and w.passage_widget.source[0] is g
    assert widget.source==w.geometry_sources['actual']
    assert widget.measurements.radii[[0,-1]]==pytest.approx([130,90])
    assert w.geometry.camber.r[[0,-1]]==pytest.approx([100,160])
    assert 'Legacy radial 2D' in w.metrics_widget.plot.plotItem.titleLabel.text
    assert w.geometry_sources['legacy'].engine=='legacy_radial_2d'
    dialog=w.show_analysis_view('Selected Row Metrics');assert dialog.isVisible()
    QApplication.processEvents()
    scroll=dialog.layout().itemAt(0).widget()
    assert scroll.verticalScrollBar().maximum()==0  # Entire initial graph fits the bounded dialog.
    target=tmp_path/'RC.csv';w.export_row_xyz_to_path(target)
    with target.open(encoding='utf-8-sig',newline='') as stream:data=list(csv.DictReader(stream))
    assert {r['snapshot_hash'] for r in data}=={widget.source.snapshot_hash}
    ps=[r for r in data if r['blade_set']=='main' and r['span']=='0' and r['segment']=='PS']
    observed=np.array([[float(r[k]) for k in ('x_mm','y_mm','z_mm')] for r in ps])
    expected=g.sections[0].master_ps.xyz
    # Independent bound for rounding to the project's chosen significant digits (default 6).
    exponent=np.floor(np.log10(np.where(expected!=0,np.abs(expected),1.)))
    quantum=10.**(exponent-params.export.significant_digits+1)
    assert np.all(np.abs(observed-expected)<=.500001*quantum)
    assert np.all(observed[expected==0]==0)
    assert w.get_parameters()==params and w.undo_stack.count()==history
    for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)


def test_legacy_and_unselected_impeller_failures_do_not_block_current_rc(window,monkeypatch,tmp_path):
    w=window;old=w.geometry;old_xyz=w.diffuser_geometry.sections[0].master_ps.xyz.copy()
    def unavailable(*args,**kwargs):raise ValueError('unrelated reference calculation failed')
    monkeypatch.setattr(w.designer,'generate_diffuser',unavailable)
    monkeypatch.setattr(w.designer,'generate_3d',unavailable)
    box=w.angle_editor.table.cellWidget(1,1);box.setValue(box.value()+2);box.editingFinished.emit()
    w.update_geometry()
    assert w.geometry is old  # Historical object retained for API compatibility, not current metrics.
    assert w.metrics_widget.geometry is None and not w.metrics_widget.table.rowCount()
    assert w.curvature_plot.geometry is None and 'legacy' not in w.geometry_sources
    assert 'unavailable' in w.metrics_widget.toolTip()
    assert w.row_metrics_widget.source is not None and w.impeller_geometry is None
    assert w._selected_3d_geometry is w.diffuser_geometry and w.passage_widget.source[0] is w.diffuser_geometry
    assert not np.allclose(old_xyz,w.diffuser_geometry.sections[0].master_ps.xyz)
    np.testing.assert_array_equal(w.blade_plot.curves['PS'].xData,w.diffuser_geometry.sections[0].master_ps.x)
    assert 'LEGACY 2D ERROR' in w.messages.toPlainText()
    w.export_row_xyz_to_path(tmp_path/'actual.csv')
    assert (tmp_path/'actual.csv').is_file()


def test_real_invalid_legacy_radius_does_not_block_rc_metrics_or_xyz(window, monkeypatch, tmp_path):
    w = window
    params = deepcopy(w.get_parameters())
    expected = w.diffuser_geometry.sections[0].master_ps.xyz.copy()
    params.geometry.r_le = -1
    params.geometry.r_te = -2
    # Inject input only: both geometry engines and the CSV writer run normally.
    monkeypatch.setattr(w, 'get_parameters', lambda: deepcopy(params))
    w.update_geometry()
    assert 'LEGACY 2D ERROR' in w.messages.toPlainText()
    assert 'legacy' not in w.geometry_sources
    assert w.row_metrics_widget.geometry is w.diffuser_geometry
    assert w.row_metrics_widget.source.row_name == 'RC'
    np.testing.assert_array_equal(w.diffuser_geometry.sections[0].master_ps.xyz, expected)
    assert w.row_metrics_widget.measurements.radii[[0, -1]] == pytest.approx([130, 90])
    target = tmp_path / 'valid-rc.csv'
    w.export_row_xyz_to_path(target)
    with target.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert rows and {r['row_name'] for r in rows} == {'RC'}
    assert {r['snapshot_hash'] for r in rows} == {w.geometry_sources['actual'].snapshot_hash}


def test_invalid_current_shape_invalidates_measurements_and_protects_xyz_export(window,tmp_path):
    w=window;target=tmp_path/'RC.csv';w.export_row_xyz_to_path(target);before=target.read_bytes()
    previous=w.diffuser_geometry
    box=w.meridional_editor.blade_edges.row_controls['row-3','trailing_edge','hub'];box.setValue(.1)
    w.update_geometry()
    assert w.diffuser_geometry is previous and w.row_metrics_widget.source is None
    assert w.passage_widget.source is None and 'actual' not in w.geometry_sources
    assert w.geometry_sources['legacy'].engine=='legacy_radial_2d'
    with pytest.raises(ValueError):w.export_row_xyz_to_path(target)
    assert target.read_bytes()==before


def test_impeller_splitter_tip_selection_and_edit_refresh_change_only_result_identity(window):
    w=window;w.select_blade_row('row-1');w.timer.stop();widget=w.row_metrics_widget
    before=deepcopy(w.get_parameters());history=w.undo_stack.count()
    index=widget.section_choice.findData('Splitter:1')
    assert index>=0
    widget.section_choice.setCurrentIndex(index)
    np.testing.assert_array_equal(widget.measurements.radii,w.impeller_geometry.splitter_sections[-1].camber.r)
    assert w.get_parameters()==before and w.undo_stack.count()==history
    old_hash=widget.source.snapshot_hash
    box=w.angle_editor.table.cellWidget(1,1);box.setValue(box.value()+1);box.editingFinished.emit()
    assert widget.source is None and not widget.section_choice.isEnabled()
    assert widget.identity.toolTip()==''
    w.update_geometry();assert widget.source.snapshot_hash!=old_hash
    w.cad_editor.radius.setValue(2.)
    assert widget.source is None
    widget.refresh_button.click();assert widget.source is not None
    assert widget.section_choice.currentData()=='Splitter:1'
    assert widget.source==geometry_source(w.get_parameters(),'meridional_3d')


def test_optimization_result_and_baseline_are_explicit_legacy_snapshots(window):
    w=window;other=w.open_optimization_mode();o=other.optimization_widget
    assert o.baseline_source.engine=='legacy_radial_2d'
    before=o.baseline_source
    other.angle_editor.move_point(1,.3,25);other.update_geometry()
    assert o.baseline_source is before
    o.preview_candidate()
    assert o.last_result is not None and o.candidate_source.engine=='legacy_radial_2d'
    assert o.candidate_source.snapshot_hash in o.report.toPlainText()


@pytest.mark.parametrize('contour',[False,True])
def test_legacy_csv_bytes_are_unchanged_by_actual_measurements(window,tmp_path,contour):
    from blade_designer.geometry.designer import BladeDesigner
    from blade_designer.fileio.csv_export import export_contour_csv,export_segments_csv
    w=window;p=w.get_parameters();legacy=BladeDesigner().generate_diffuser(p)
    menu=next(a.menu() for a in w.file_menu.actions() if a.text()=='Export')
    assert all('Legacy radial 2D' in a.toolTip() for a in menu.actions()[:2])
    expected=tmp_path/'compatibility.csv';actual=tmp_path/'gui.csv'
    (export_contour_csv if contour else export_segments_csv)(expected,legacy,p.export)
    w.export_to_path(actual,contour=contour)
    assert actual.read_bytes()==expected.read_bytes()
    assert 'legacy radial 2D' in w.statusBar().currentMessage()
    w._select_meridional();assert w.row_metrics_widget.source is None


@pytest.mark.parametrize('kind',['blade_angle','thickness'])
def test_current_cell_updates_endpoint_delete_guard_without_a_selection_change(kind):
    from PySide6.QtCore import QItemSelectionModel
    from blade_designer.gui.control_point_editor import ControlPointEditor
    from blade_designer.models.parameters import DistributionPoint
    app=QApplication.instance() or QApplication([]);e=ControlPointEditor(kind)
    try:
        e.set_points([DistributionPoint(0,1),DistributionPoint(.5,4),DistributionPoint(1,1)])
        e.table.selectRow(1);assert e.delete_button.isEnabled()
        selection=e.table.selectionModel()
        selection.setCurrentIndex(e.table.model().index(0,0),QItemSelectionModel.SelectionFlag.NoUpdate)
        assert not e.delete_button.isEnabled()
        e.delete_button.click();assert len(e.get_points())==3
        selection.setCurrentIndex(e.table.model().index(1,0),QItemSelectionModel.SelectionFlag.NoUpdate)
        assert e.delete_button.isEnabled()
        e.delete_button.click();assert [p.m_norm for p in e.get_points()]==[0,1]
    finally:e.close();e.deleteLater();app.processEvents()
