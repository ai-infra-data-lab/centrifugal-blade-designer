"""Shared actual main/splitter graphs, independent controls and stable data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
import pytest
import pyqtgraph as pg
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import SplitterParameters
from test_impeller_te_rake import radial_parameters


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([]);w=MainWindow();w.show();app.processEvents()
    p=radial_parameters();p.splitter=SplitterParameters(.37,.68,.5,1.4)
    w.set_parameters(p);w.update_geometry();w._reset_history()
    yield w,app
    for dialog in w._tool_dialogs.values():dialog.close()
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


@pytest.mark.parametrize('kind',['blade_angle','thickness'])
def test_shared_curves_and_controls_edit_both_without_cross_writing(window,tmp_path,kind):
    w,app=window;host=w.angle_editor if kind=='blade_angle' else w.thickness_editor
    w.tabs.setCurrentWidget(host);app.processEvents()
    assert len(host.references)==3 and host.groups.isTabVisible(1)
    before=deepcopy(w.get_parameters());history=w.undo_stack.count()
    host.groups.setCurrentIndex(1);app.processEvents()
    assert w.get_parameters()==before and w.undo_stack.count()==history
    w.splitter_editor.independent.setChecked(True);w.update_geometry();app.processEvents()
    peer=w.splitter_editor.angle_editor if kind=='blade_angle' else w.splitter_editor.thickness_editor
    assert host.peer is peer and peer.plot is host.plot
    assert not host.references and host.splitter_page.currentWidget() is peer.scroll
    assert host.findChildren(pg.PlotWidget)==[host.plot]
    for span,editor in peer.series.items():
        assert editor.plot is host.plot and editor.curve in host.plot.items() and editor.handles.isVisible()
        assert not host.series[span].handles.isVisible()
        source=next(s for s in w.impeller_geometry.splitter_sections if s.span==span)
        start=(1-span)*.37+span*.68
        np.testing.assert_array_equal(editor.curve.xData,start+(1-start)*source.camber.m_blade_norm)
        np.testing.assert_array_equal(editor.curve.yData,source.beta_m_deg if kind=='blade_angle' else source.thickness/1.4)
        assert editor.table.cellWidget(0,0).value()==pytest.approx(start)
    main=[s.master_ps.xyz.copy() for s in w.impeller_geometry.sections]
    before=deepcopy(w.get_parameters());peer.series[0].move_point(0,0.,24. if kind=='blade_angle' else 1.7)
    w.update_geometry();after=deepcopy(w.get_parameters())
    assert before!=after
    for a,b in zip(main,w.impeller_geometry.sections):np.testing.assert_array_equal(a,b.master_ps.xyz)
    w.undo();assert w.get_parameters()==before
    w.redo();assert w.get_parameters()==after
    split=deepcopy(w.get_parameters().splitter.sections)
    host.groups.setCurrentIndex(0);app.processEvents()
    assert host.series[0].handles.isVisible() and not peer.series[0].handles.isVisible()
    host.series[0].move_point(0,0,26. if kind=='blade_angle' else 1.2);w.update_geometry()
    assert w.get_parameters().splitter.sections==split
    path=tmp_path/(kind+'.json');w.save_to_path(path);saved=deepcopy(w.get_parameters())
    w.load_from_path(path);assert w.get_parameters()==saved
    assert peer.plot is host.plot


def test_modes_rebuild_cleanly_and_settings_link_to_shared_editor(window):
    w,app=window;e=w.splitter_editor
    e.independent.setChecked(True);w.update_geometry()
    e.blade_angle_button.click();app.processEvents()
    assert w.tabs.currentWidget() is w.angle_editor and w.angle_editor.groups.currentIndex()==1
    e.thickness_button.click();app.processEvents()
    assert w.tabs.currentWidget() is w.thickness_editor and w.thickness_editor.groups.currentIndex()==1
    assert e.distributions.isHidden()
    for _ in range(3):
        w.view_mode.setCurrentIndex(1);w.update_geometry();app.processEvents()
        assert not w.angle_editor.groups.isTabVisible(1)
        assert all(not editor.curve.isVisible() for editor in e.angle_editor.series.values())
        w.view_mode.setCurrentIndex(0);w.update_geometry();app.processEvents()
        assert w.angle_editor.groups.isTabVisible(1)
        assert len(w.angle_editor.plot.listDataItems())==6
        assert len(w.angle_editor.legend.items)==6
    e.independent.setChecked(False);w.update_geometry()
    assert len(w.angle_editor.references)==3
    assert all(not editor.curve.isVisible() for editor in e.angle_editor.series.values())
    e.independent.setChecked(True);w.update_geometry();app.processEvents()
    assert not w.angle_editor.references and len(w.angle_editor.legend.items)==6
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
    assert w.angle_editor.findChildren(pg.PlotWidget)==[w.angle_editor.plot]
