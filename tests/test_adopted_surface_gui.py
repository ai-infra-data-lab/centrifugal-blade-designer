import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.cad_surface_reference_widget import CadSurfaceReferenceWidget
from blade_designer.models.parameters import BladeParameters,SplitterParameters
from blade_designer.fileio.geometry_source import geometry_source
from test_cad_reference_report import cad_report


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def test_adopted_mode_group_change_retains_snapshot_camera_and_design(app,monkeypatch):
    p=BladeParameters();p.splitter=SplitterParameters();before=deepcopy(p)
    report=cad_report(geometry_source(p,'meridional_3d').snapshot_hash)
    widget=CadSurfaceReferenceWidget(lambda:p,cad_report=lambda:report)
    def forbidden(*args,**kwargs):raise AssertionError('Adopted reference cannot launch CAD or write files')
    from blade_designer.cad import client
    monkeypatch.setattr(client,'prepare_job',forbidden)
    for method in ('write_text','write_bytes','mkdir'):monkeypatch.setattr(Path,method,forbidden)
    try:
        widget.show();widget.refresh();app.processEvents();widget.preview._show_fit.stop()
        widget.preview.camera_position['azimuth']=71.
        camera=deepcopy(widget.preview.camera_position)
        widget.adopted.setChecked(True)
        assert widget.result is not None and not widget.density.isEnabled()
        assert 'LE=33, PS=65, TE=129, SS=257' in widget.info.text()
        widget.group.setCurrentIndex(1);app.processEvents()
        assert 'LE=513, PS=129, TE=65, SS=33' in widget.info.text()
        for key,value in camera.items():np.testing.assert_array_equal(widget.preview.camera_position[key],value)
        assert p==before
        widget.adopted.setChecked(False);assert widget.density.isEnabled() and 'grid 65' in widget.info.text()
    finally:widget.close();widget.deleteLater();app.processEvents()


@pytest.mark.parametrize('bad',['missing','stale','failure','splitter'])
def test_bad_adopted_report_hides_preview_instead_of_using_fixed_density(app,bad):
    p=BladeParameters();p.splitter=SplitterParameters()
    report=cad_report(geometry_source(p,'meridional_3d').snapshot_hash)
    if bad=='missing':report=None
    elif bad=='stale':report['parameter_snapshot_hash']='0'*64
    elif bad=='failure':report['overall']='FAIL'
    else:del report['checks']['blade_solids']['splitter']
    widget=CadSurfaceReferenceWidget(lambda:p,cad_report=lambda:report)
    try:
        widget.refresh()
        if bad=='splitter':widget.group.setCurrentIndex(1)
        widget.adopted.setChecked(True)
        assert widget.result is None and widget.preview.isHidden() and '表示できません' in widget.info.text()
        widget.adopted.setChecked(False);widget.refresh()
        assert widget.result is not None and 'grid 65' in widget.info.text()
    finally:widget.close();widget.deleteLater();app.processEvents()


def test_main_window_uses_latest_completed_report_without_changing_design(app,tmp_path):
    from blade_designer.gui.main_window import MainWindow
    from test_standard_menus_gui import dispose
    w=MainWindow()
    try:
        w.timer.stop();w.show_cad_surface_reference();widget=w.cad_surface_reference_widget
        before=deepcopy(w.get_parameters());history=w.undo_stack.count()
        digest=widget.result['source'].snapshot_hash
        report=cad_report(digest)
        w._cad_finished(tmp_path,before,None,report)
        widget.adopted.setChecked(True)
        assert widget.result is not None and 'CAD adopted' in widget.info.text()
        report['checks']['blade_solids']['main']['surface_grid_counts']['le']=513
        widget.refresh();assert 'LE=33' in widget.info.text()  # Stored result owns its copy.
        w._cad_finished(tmp_path,before,None,{'overall':'FAIL','error':{'message':'kernel failure'}})
        assert widget.result is None and widget.preview.isHidden()
        assert w.get_parameters()==before and w.undo_stack.count()==history
    finally:dispose(w,app)
