"""Default RC and both central projections use the exact same master curves."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from copy import deepcopy
import hashlib
import numpy as np
from PySide6.QtWidgets import QApplication
from main import create_window,parse_arguments
from blade_designer.fileio.project_io import load_project
from blade_designer.geometry.annulus import project_annulus
from test_tip_clearance_gui import dispose

TEMPLATE=Path(__file__).resolve().parents[1]/'blade_designer/defaults/default_project.json'


def assert_projection(w):
    g=w.diffuser_geometry;section=g.sections[0]
    np.testing.assert_array_equal(w.blade_plot.camber_curve.xData,section.camber.x)
    np.testing.assert_array_equal(w.blade_plot.camber_curve.yData,section.camber.y)
    for name,line in w.blade_plot.curves.items():
        c=getattr(section,'master_'+name.lower());x,y=line.getData()
        np.testing.assert_array_equal(x,c.x);np.testing.assert_array_equal(y,c.y)
        preview=w.model_preview_3d.base_lines['Hub '+name.lower()][0]
        np.testing.assert_array_equal(np.column_stack((x,y)),preview[:,:2])
        count=w.get_parameters().geometry.vane_count
        ex,ey=project_annulus(c.x,c.y,c.z,count,'XY')
        ax,ay=w.annulus_plot.curves[name].getData()
        np.testing.assert_array_equal(ax,ex);np.testing.assert_array_equal(ay,ey)
    assert w.blade_plot.throat_line.xData is None or not len(w.blade_plot.throat_line.xData)
    assert w.annulus_plot.throat_line.xData is None or not len(w.annulus_plot.throat_line.xData)


def test_template_is_requested_three_row_design_and_new_restores_rc():
    app=QApplication.instance() or QApplication([])
    # Git may convert CRLF to LF on another PC; the design data must agree.
    canonical=TEMPLATE.read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(canonical).hexdigest()=='67d53be838887c67e2f310a3bf26e99aed854f8d27082dd2b534b7679ee6c0db'
    p=load_project(TEMPLATE)
    assert [(r.identifier,r.name,r.kind) for r in p.blade_rows]==[
        ('row-1','Impeller','impeller'),('row-2','Diffuser','diffuser'),('row-3','RC','diffuser')]
    w=create_window(parse_arguments([]))
    try:
        assert w._active_row=='row-3' and w.project_path is None
        np.testing.assert_allclose(w.diffuser_geometry.sections[0].camber.r[[0,-1]],[130,90],atol=1e-7)
        assert_projection(w)
        assert 'RC' in w.annulus_plot.plotItem.titleLabel.text
        w.select_blade_row('row-1');w.new_project()
        assert w._active_row=='row-3';assert_projection(w)
    finally:dispose(w,app)


def test_rc_edit_undo_json_and_row_switch_keep_central_shapes_consistent(tmp_path):
    app=QApplication.instance() or QApplication([]);w=create_window(parse_arguments([]))
    try:
        original=deepcopy(w.get_parameters());before=w.diffuser_geometry.sections[0].master_ps.xyz.copy()
        for row in ('row-2','row-1','row-3'):
            w.select_blade_row(row)
            if w._editing_target==1:assert_projection(w)
        assert w.get_parameters().diffuser_edges==original.diffuser_edges
        w.annulus_2d.setChecked(True);w.annulus_3d.setChecked(True);assert_projection(w)
        editor=w.angle_editor.table.cellWidget(1,1)
        editor.setValue(editor.value()+3);editor.editingFinished.emit();w.update_geometry()
        assert_projection(w)
        changed=w.diffuser_geometry.sections[0].master_ps.xyz.copy()
        assert not np.allclose(changed,before)
        w.undo();assert_projection(w)
        np.testing.assert_array_equal(w.diffuser_geometry.sections[0].master_ps.xyz,before)
        w.redo();assert_projection(w)
        target=tmp_path/'RC.json';w.save_to_path(target);w.load_from_path(target)
        assert_projection(w)
        np.testing.assert_array_equal(w.diffuser_geometry.sections[0].master_ps.xyz,changed)
    finally:dispose(w,app)


def test_legacy_radial_dimensions_do_not_replace_meridional_preview():
    app=QApplication.instance() or QApplication([]);w=create_window(parse_arguments([]))
    try:
        old=w.diffuser_geometry.sections[0].camber.xyz.copy()
        w.panel.controls['r_le'].setValue(105);w.update_geometry()
        assert w.geometry.camber.r[0]==105  # Legacy diagnostics/export remain compatible.
        np.testing.assert_array_equal(w.diffuser_geometry.sections[0].camber.xyz,old)
        assert_projection(w)
    finally:dispose(w,app)
