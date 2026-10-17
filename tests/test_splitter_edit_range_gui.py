"""Splitter controls occupy LE..TE without renormalizing the main 0..1 axis."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from blade_designer.models.parameters import DistributionPoint,SplitterParameters
from blade_designer.geometry.splitter import splitter_edit_points
from blade_designer.geometry.distributions import interpolate_beta_m_deg
from blade_designer.gui.splitter_distribution_editor import SplitterControlPointEditor
from blade_designer.gui.main_window import MainWindow
from test_impeller_te_rake import radial_parameters


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def controls():return [DistributionPoint(x,y) for x,y in zip([0,.2,.4,.6,.8,1],[20,35,24,38,22,25])]


def positions(editor):return [editor.table.cellWidget(i,0).value() for i in range(editor.table.rowCount())]


@pytest.mark.parametrize('start',[.4,.53,.99999])
def test_boundary_on_main_axis_has_original_interpolated_value(start):
    points=controls();before=deepcopy(points)
    visible=splitter_edit_points(points,start)
    assert visible[0].m_norm==start and visible[-1].m_norm==1
    assert all(p.m_norm>=start for p in visible)
    assert visible[0].value==pytest.approx(interpolate_beta_m_deg(np.array([start]),points)[0],abs=1e-12)
    assert points==before


@pytest.mark.parametrize('start',[-.1,1.,float('nan')])
def test_invalid_edit_start_rejected(start):
    with pytest.raises(ValueError,match='editing start'):splitter_edit_points(controls(),start)


@pytest.mark.parametrize('kind',['blade_angle','thickness'])
def test_hidden_data_is_retained_but_visible_le_is_fixed_on_active_edits(app,kind):
    e=SplitterControlPointEditor(kind);e.set_start_fraction(.53);e.set_points(controls())
    try:
        source=controls();assert e.get_points()==source
        assert positions(e)==pytest.approx([.53,.6,.8,1])
        assert not e.table.cellWidget(0,0).isEnabled() and not e.table.cellWidget(3,0).isEnabled()
        np.testing.assert_allclose(e.handles.scatter.getData()[0],[.53,.6,.8,1])
        # Editing a downstream control fixes the displayed LE as a real
        # endpoint; hidden upstream points must no longer move its value.
        original_le=e.table.cellWidget(0,1).value()
        e.table.cellWidget(1,1).setValue(31.)
        full=e.get_points()
        assert [p for p in full if p.m_norm<.53]==[p for p in source if p.m_norm<.53]
        assert next(p for p in full if p.m_norm==.53).value==pytest.approx(original_le,abs=1e-11)
        assert e.table.cellWidget(0,1).value()==original_le
        # LE value is an editable boundary; its X cannot be dragged upstream.
        e.move_point(0,0.,29.)
        full=e.get_points();assert positions(e)[0]==.53
        assert next(p for p in full if p.m_norm==.53).value==29.
        assert interpolate_beta_m_deg(np.array([.53]),full)[0]==pytest.approx(29.)
        e.table.cellWidget(1,0).setValue(.1)
        assert .53<positions(e)[1]<positions(e)[2]
        assert not e.message.text()
    finally:e.close();e.deleteLater();app.processEvents()


def test_add_delete_and_start_changes_never_edit_upstream_support(app):
    e=SplitterControlPointEditor('blade_angle');e.set_start_fraction(.53);e.set_points(controls())
    try:
        original=e.get_points();e.add_point()
        assert e.table.rowCount()==5 and all(x>=.53 for x in positions(e))
        selected=e.table.currentRow();assert 0<selected<4
        inserted=positions(e)[selected]
        assert any(abs(p.m_norm-inserted)<1e-12 for p in e.get_points())
        e.delete_point();assert e.table.rowCount()==4
        assert [p for p in e.get_points() if p.m_norm<.53]==[p for p in original if p.m_norm<.53]
        for row in (0,3):
            e.table.selectRow(row);before=e.get_points();e.delete_point();assert e.get_points()==before
        before=e.get_points()
        for start in (.72,.25,.99,.53):
            e.set_start_fraction(start)
            assert positions(e)[0]==pytest.approx(start) and positions(e)[-1]==1
            assert e.get_points()==before
    finally:e.close();e.deleteLater();app.processEvents()


def test_loaded_boundary_precision_and_range_changes_do_not_emit_edits(app):
    e=SplitterControlPointEditor('blade_angle');e.set_points(controls());changes=[]
    e.pointsChanged.connect(lambda:changes.append(True))
    try:
        start=.234567890123456;e.set_start_fraction(start)
        assert e._points[0].m_norm==start
        assert e.get_points()==controls() and changes==[]
        e.move_point(0,0,31.)
        assert next(p for p in e.get_points() if p.m_norm==start).value==31.
        saved=e.get_points();e.set_start_fraction(.8);e.set_start_fraction(start)
        assert e.get_points()==saved and len(changes)==1
    finally:e.close();e.deleteLater();app.processEvents()


def test_invalid_source_is_preserved_without_fabricating_a_boundary(app):
    e=SplitterControlPointEditor('blade_angle');e.set_start_fraction(.5)
    try:
        invalid=[DistributionPoint(x,20) for x in (0,.6,.4,1)]
        e.set_points(invalid)
        assert e.get_points()==invalid and 'strictly' in e.message.text()
        assert positions(e)==[.6,1]
        e.set_points(controls());e.table.cellWidget(0,1).setValue(90)
        assert '85' in e.message.text() and e.get_points()[0]==controls()[0]
    finally:e.close();e.deleteLater();app.processEvents()


def test_copy_active_spans_le_edit_start_undo_reload_and_recopy(app,tmp_path):
    w=MainWindow();w.show();app.processEvents()
    try:
        p=radial_parameters();p.splitter=SplitterParameters(.37,.68,.5,1.)
        for profile in p.sections:
            profile.blade_angle.points=controls()
        p.blade_angle=p.sections[0].blade_angle
        w.set_parameters(p);w.update_geometry();w._reset_history()
        e=w.splitter_editor
        w.tabs.setCurrentIndex(next(i for i in range(w.tabs.count()) if w.tabs.tabText(i)=='Splitter'))
        main=[s.master_ps.xyz.copy() for s in w.impeller_geometry.sections]
        e.independent.setChecked(True);w.update_geometry()
        for section in w.impeller_geometry.splitter_sections:
            assert np.isfinite(section.master_ps.xyz).all()
            np.testing.assert_array_equal(section.master_te.r,np.full(len(section.master_te.r),120.))
        assert w.get_parameters().splitter.sections==w.get_parameters().sections
        for editor in (e.angle_editor,e.thickness_editor):
            for span,series in editor.series.items():
                start=(1-span)*.37+span*.68
                assert positions(series)[0]==pytest.approx(start) and positions(series)[-1]==1
                assert all(x>=start-1e-12 for x in positions(series))
                assert editor.plot.getViewBox().viewRange()[0][0]<.01
        before=deepcopy(w.get_parameters());history=w.undo_stack.count()
        box=e.angle_editor.series[0].table.cellWidget(0,1)
        box.setFocus();box.selectAll();QTest.keyClicks(box,'27')
        assert w.get_parameters()==before
        QTest.keyClick(box,Qt.Key.Key_Return);w.update_geometry()
        assert w.undo_stack.count()==history+1
        assert w.impeller_geometry.splitter_sections[0].beta_m_deg[0]==pytest.approx(27.)
        for a,b in zip(main,w.impeller_geometry.sections):np.testing.assert_array_equal(a,b.master_ps.xyz)
        w.undo();assert w.get_parameters()==before
        w.redo();e.controls['hub_start_fraction'].setValue(45);w.update_geometry()
        assert positions(e.angle_editor.series[0])[0]==.45
        # Newly created LE fields keep Enter and Ctrl+Z behavior after range changes.
        previous=deepcopy(w.get_parameters());box=e.angle_editor.series[0].table.cellWidget(0,1)
        box.setFocus();box.selectAll();QTest.keyClicks(box,'26');QTest.keyClick(box,Qt.Key.Key_Return)
        QTest.keyClick(box,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
        assert w.get_parameters()==previous
        path=tmp_path/'active-range.json';w.save_to_path(path);w.load_from_path(path)
        assert w.get_parameters()==previous
        assert positions(e.angle_editor.series[0])[0]==.45
        e.copy_button.click();w.update_geometry()
        copied=deepcopy(w.get_parameters());copied.splitter.sections=deepcopy(copied.sections)
        from blade_designer.geometry.geometry_3d import generate_impeller
        expected=generate_impeller(copied)
        for a,b in zip(expected.splitter_sections,w.impeller_geometry.splitter_sections):np.testing.assert_array_equal(a.master_ps.xyz,b.master_ps.xyz)
        assert all(x>=.45 for x in positions(e.angle_editor.series[0]))
    finally:
        for dialog in w._tool_dialogs.values():dialog.close()
        w.timer.stop();w.close();w.deleteLater();app.processEvents()
