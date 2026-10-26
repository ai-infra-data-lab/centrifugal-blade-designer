"""Qt integration: independent walls, chained poses and no synthetic blades."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.blade_rows import row_parameters
from blade_designer.geometry.meridional_segments import generate_meridional
from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def test_add_edit_follow_select_roundtrip_and_undo(window,tmp_path):
    w=window;before=deepcopy(w.get_parameters())
    w.add_blade_row('meridional','Outlet duct')
    p=w.get_parameters();identifier=p.active_blade_row
    row=p.blade_rows[-1]
    assert row.kind=='meridional' and row.independent_meridional and row.upstream_row=='row-1'
    assert [w.tabs.tabText(i) for i in range(w.tabs.count()) if w.tabs.isTabVisible(i)]==['Meridional']
    assert not w.meridional_editor.blade_edges.isVisible()
    assert w.meridional_editor.blade_edges.table.rowCount()==0
    assert not w.meridional_editor.start_controls['start_z'].isEnabled()
    assert w._selected_3d_geometry.sections==[]
    assert p.hub==before.hub and p.shroud==before.shroud
    assert w.central_views.currentWidget() is w.element_meridional_view
    assert w.element_meridional_view.wall_lines
    assert 'ERROR' not in w.messages.toPlainText()
    # Local segment dimensions affect neither shared walls nor parent definitions.
    w.meridional_editor.curves[0].segments[0].length=31
    w.commit_edit();w.update_geometry()
    edited=w.get_parameters()
    assert edited.blade_rows[-1].parameters.hub.segments[0].length==31
    assert edited.hub==before.hub
    w._select_meridional()
    assert w.get_parameters().hub==before.hub
    w.select_blade_row(identifier)
    assert w.get_parameters()==edited
    # Upstream edits move the connected child without changing its raw definition.
    w._select_meridional()
    w.meridional_editor.curves[0].start_z+=3
    w.commit_edit();w.select_blade_row(identifier)
    moved=w.get_parameters()
    old=row_parameters(edited,edited.blade_rows[-1])
    new=row_parameters(moved,moved.blade_rows[-1])
    assert new.hub.start_z==pytest.approx(old.hub.start_z+3)
    assert moved.blade_rows[-1].parameters==edited.blade_rows[-1].parameters
    # Detach freezes the effective pose; undo restores the connection.
    w.element_walls_editor.upstream.setCurrentIndex(0)
    detached=w.get_parameters()
    assert detached.blade_rows[-1].upstream_row is None
    np.testing.assert_allclose(generate_meridional(detached.blade_rows[-1].parameters.hub).segments[0].start.zr,
                               generate_meridional(new.hub).segments[0].start.zr,atol=1e-10)
    w.undo();assert w.get_parameters().blade_rows[-1].upstream_row=='row-1'
    w.redo();assert w.get_parameters()==detached
    path=tmp_path/'elements.json';w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters()==detached
    options=CoordinateCsvOptions(include_blades=False,include_hub=True,include_shroud=True,extension='txt')
    files=w.export_coordinate_to_path(tmp_path/'walls.txt',options)
    assert files and (tmp_path/'walls.txt').is_file()
    with pytest.raises(ValueError,match='no blade'):
        w.export_row_xyz_to_path(tmp_path/'no.csv')
    assert not (tmp_path/'no.csv').exists()


def test_parent_delete_is_blocked_and_links_survive_rename_and_reorder(window):
    w=window;w.add_blade_row('meridional','Duct')
    identifier=w.get_parameters().active_blade_row
    w.rename_blade_row(identifier,'Renamed');w.move_blade_row(-1)
    assert next(r for r in w.get_parameters().blade_rows if r.identifier==identifier).upstream_row=='row-1'
    w.select_blade_row('row-1');before=deepcopy(w.get_parameters())
    w.delete_blade_row()
    assert w.get_parameters()==before
    assert '後続要素' in w.messages.toPlainText()


def test_existing_blade_can_use_independent_connected_walls_without_changing_profiles(window):
    w=window;w.add_blade_row('meridional','Duct');duct_id=w.get_parameters().active_blade_row
    w.select_blade_row('row-2');before=deepcopy(w.get_parameters())
    box=w.element_walls_editor.independent
    box.blockSignals(True);box.setChecked(True);box.blockSignals(False);w._element_walls_changed()
    combo=w.element_walls_editor.upstream
    combo.blockSignals(True);combo.setCurrentIndex(combo.findData(duct_id));combo.blockSignals(False);w._element_walls_changed()
    after=w.get_parameters();row=next(r for r in after.blade_rows if r.identifier=='row-2')
    assert row.independent_meridional and row.upstream_row==duct_id
    assert row.parameters.diffuser_profile==before.blade_rows[1].parameters.diffuser_profile
    from blade_designer.geometry.geometry_3d import generate_diffuser_3d
    geometry=generate_diffuser_3d(after)
    assert len(geometry.sections)==2 and geometry is not None
    parent=row_parameters(after,next(r for r in after.blade_rows if r.identifier==duct_id))
    for side in ('hub','shroud'):
        a=generate_meridional(getattr(parent,side)).segments[-1]
        b=getattr(geometry,side).segments[0]
        np.testing.assert_allclose(a.end.zr,b.start.zr,atol=1e-10)
        np.testing.assert_allclose(a.end_tangent,b.start_tangent,atol=1e-12)
    w.tabs.setCurrentIndex(next(i for i in range(w.tabs.count()) if w.tabs.tabText(i)=='Meridional'));w.update_geometry()
    assert w.central_views.currentWidget() is w.element_meridional_view
    assert len(w.element_meridional_view.edge_lines)==2
    private=deepcopy(row.parameters)
    w._select_meridional();w.get_parameters();w.select_blade_row('row-2')
    assert next(r for r in w.get_parameters().blade_rows if r.identifier=='row-2').parameters==private
