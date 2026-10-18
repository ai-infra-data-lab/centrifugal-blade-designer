"""Read-only row distance displays track R/Z edits, ownership and history."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.fileio.project_io import load_project,save_project
from blade_designer.geometry.meridional_segments import generate_meridional,sample_meridional


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.load_from_path(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json')
    w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_default_rows_are_integer_intervals_and_selection_is_read_only(window):
    w=window;e=w.meridional_editor.blade_edges;before=deepcopy(w.get_parameters())
    assert e.coordinate_map.order==('row-1','row-2','row-3')
    assert all(f'{i}–{i+1} {row.name}' in e.scale_label.text() for i,row in enumerate(before.blade_rows))
    for key,item in e.position_items.items():
        assert item.text()!='—' and not item.flags() & Qt.ItemFlag.ItemIsEditable
        assert float(item.text())==pytest.approx(e.row_positions[key],rel=1e-7)
    editor=w.meridional_editor
    assert editor.table.horizontalHeader().visualIndex(6)==2
    assert e.table.horizontalHeader().visualIndex(4)==2
    for wall in (0,1):
        editor.selector.setCurrentIndex(wall)
        assert editor.table.item(0,6).text().startswith('0 →')
        assert editor.table.item(4,6).text()=='2 → 3'
    w._select_meridional();w.update_geometry()
    assert '2–3 RC' in editor.context.row_scale.text()
    assert w.get_parameters()==before


def test_rz_edit_updates_local_le_position_one_undo_and_json(window,tmp_path):
    w=window;w.select_blade_row('row-2');w._select_meridional()
    before=deepcopy(w.get_parameters());e=w.meridional_editor.blade_edges
    start,end=e.coordinate_map.intervals['hub']['row-2'];distance=start+.05*(end-start)
    hub=generate_meridional(before.hub);z,r=sample_meridional(hub,np.array([distance]))[0]
    e.all_coordinate_controls['row-2','leading_edge','hub','r'].setValue(r)
    e.all_coordinate_controls['row-2','leading_edge','hub','z'].setValue(z)
    assert w.get_parameters()==before
    count=w.undo_stack.count();e.apply_button.click();w.update_geometry()
    after=deepcopy(w.get_parameters())
    assert e.row_positions['row-2','leading_edge','hub']==pytest.approx(1.05,abs=1e-11)
    assert after.diffuser_edges.leading_edge.hub_m_flow_norm==pytest.approx(distance/hub.length,abs=1e-12)
    assert w.undo_stack.count()==count+1
    w.undo();w.update_geometry();assert w.get_parameters()==before
    w.redo();w.update_geometry();assert w.get_parameters()==after
    path=tmp_path/'local-display.json';w.save_to_path(path);assert load_project(path)==after
    w.load_from_path(path);w.update_geometry()
    assert e.row_positions['row-2','leading_edge','hub']==pytest.approx(1.05,abs=1e-11)


def test_reorder_rename_uses_physical_inlet_order_not_list_order(window):
    w=window;p=deepcopy(w.get_parameters());expected=dict(w.meridional_editor.blade_edges.row_positions)
    p.blade_rows.reverse();p.blade_rows[0].name='Return channel'
    w.set_parameters(p);w.update_geometry();e=w.meridional_editor.blade_edges
    assert e.coordinate_map.order==('row-1','row-2','row-3')
    assert e.row_positions==expected
    assert '2–3 Return channel' in e.scale_label.text()


def test_missing_or_reversed_ownership_is_unavailable_without_changing_edges(window):
    w=window;baseline=deepcopy(w.get_parameters())
    for mode in ('missing','reversed'):
        p=deepcopy(baseline);edges=deepcopy(p.impeller_edges)
        if mode=='missing':p.shroud.segments[-1].blade_row=None
        else:
            for s in p.shroud.segments:
                if s.blade_row=='row-1':s.blade_row='row-2'
                elif s.blade_row=='row-2':s.blade_row='row-1'
        w.set_parameters(p);w.update_geometry();e=w.meridional_editor.blade_edges
        assert e.coordinate_map is None and all(item.text()=='—' for item in e.position_items.values())
        assert e.row_positions=={} and '未設定' in e.scale_label.text()
        assert w.get_parameters().impeller_edges==edges


def test_outside_owned_range_is_displayed_and_flagged_without_clamping(window):
    e=window.meridional_editor.blade_edges
    key=('row-2','leading_edge','hub')
    e.row_controls[key].setValue(.01)
    assert e.row_positions[key]<1
    assert '範囲外' in e.position_items[key].toolTip()
    assert e.row_edges['row-2'].leading_edge.hub_m_flow_norm==.01


def test_ownership_change_and_invalid_geometry_refresh_positions(window):
    w=window;editor=w.meridional_editor;e=editor.blade_edges
    before=dict(e.row_positions)
    combo=editor.table.cellWidget(2,5);combo.setCurrentIndex(combo.findData('row-1'))
    w.update_geometry()
    assert e.coordinate_map is not None and e.row_positions!=before
    w.undo();w.update_geometry();assert e.row_positions==before
    editor.table.cellWidget(1,2).setValue(-1)
    # Existing wall input rejects a negative radius before adopting it.
    assert e.row_positions==before and editor.curves[0].segments[1].radius>0
    invalid=deepcopy(editor.get_curves());invalid[0].segments[1].radius=-1
    editor.set_curves(*invalid)
    assert e.coordinate_map is None and all(item.text()=='—' for item in e.position_items.values())
    assert all(editor.table.item(i,6).text()=='—' for i in range(editor.table.rowCount()))


def test_pending_rz_and_angle_thickness_axes_remain_unchanged(window):
    w=window;e=w.meridional_editor.blade_edges;p=deepcopy(w.get_parameters())
    key=('row-2','leading_edge','hub','r');value=e.all_coordinate_controls[key].value()+.123
    e.all_coordinate_controls[key].setValue(value)
    e.set_row_names(p.blade_rows,p.active_blade_row)
    assert e.all_coordinate_controls[key].value()==value and w.get_parameters()==p
    for editor in (w.angle_editor,w.thickness_editor):
        for series in editor.series.values():
            x,_=series.curve.getData()
            assert np.min(x)==0 and np.max(x)==1


def test_default_json_bytes_and_derived_display_state_are_not_persisted(window,tmp_path):
    source=Path(__file__).parents[1]/'blade_designer/defaults/default_project.json';data=source.read_bytes()
    p=window.get_parameters();a=tmp_path/'a.json';b=tmp_path/'b.json';save_project(a,p)
    window.meridional_editor.update_preview();save_project(b,window.get_parameters())
    assert a.read_bytes()==b.read_bytes() and source.read_bytes()==data
    assert b'row_positions' not in b.read_bytes() and b'coordinate_map' not in b.read_bytes()
