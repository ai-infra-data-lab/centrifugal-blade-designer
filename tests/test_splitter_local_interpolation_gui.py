"""Shared graph and generated blade agree after a visible endpoint edit."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import SplitterParameters
from test_impeller_te_rake import radial_parameters


@pytest.mark.parametrize('kind',['blade_angle','thickness'])
def test_editing_te_keeps_le_and_graph_matches_local_pchip_and_undo(kind,tmp_path):
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        p=radial_parameters();p.splitter=SplitterParameters(sections=deepcopy(p.sections))
        w.set_parameters(p);w.update_geometry();w._reset_history()
        host=w.angle_editor if kind=='blade_angle' else w.thickness_editor
        w.tabs.setCurrentWidget(host);host.groups.setCurrentIndex(1);app.processEvents()
        editor=host.peer.series[0];before=deepcopy(w.get_parameters())
        main=w.impeller_geometry.sections[0].master_ps.xyz.copy()
        start=editor._points[0].m_norm;le=editor._points[0].value
        assert len(editor._points)==2
        te=15. if kind=='blade_angle' else 2.3
        editor.move_point(1,1,te);w.update_geometry()
        assert editor._points[0].value==le
        section=w.impeller_geometry.splitter_sections[0]
        query=start+(1-start)*section.camber.m_blade_norm
        expected=np.interp(query,[start,1],[le,te])
        actual=section.beta_m_deg if kind=='blade_angle' else section.thickness
        np.testing.assert_allclose(actual,expected,atol=1e-12)
        np.testing.assert_array_equal(editor.curve.yData,actual)
        np.testing.assert_array_equal(w.impeller_geometry.sections[0].master_ps.xyz,main)
        stored=getattr(w.get_parameters().splitter.sections[0],kind).points
        assert next(point for point in stored if point.m_norm==start).value==le
        after=deepcopy(w.get_parameters());w.undo();assert w.get_parameters()==before
        w.redo();assert w.get_parameters()==after
        path=tmp_path/'edited.json';w.save_to_path(path);w.load_from_path(path)
        assert w.get_parameters()==after
    finally:
        w.timer.stop();w.close();w.deleteLater();app.processEvents()
