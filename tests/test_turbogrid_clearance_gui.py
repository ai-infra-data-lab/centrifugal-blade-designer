"""Export committed clearance without altering the displayed physical blade."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
from blade_designer.gui.main_window import MainWindow
from blade_designer.fileio.turbogrid_export import closed_profile
from test_turbogrid_export import read_profiles


def test_export_clearance_commits_current_values_and_reports_physical_profile(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    warnings=[];case=tmp_path/'case'
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(case))
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:warnings.append(args[-1]))
    try:
        e=w.tip_clearance_editor;e.setChecked(True)
        e.controls['le_mm'].setValue(.5);e.controls['te_mm'].setValue(1.)
        w.update_geometry();before=deepcopy(w.get_parameters())
        original=w.impeller_geometry.sections[-1].master_ps.xyz.copy()
        camera=deepcopy(w.model_preview_3d.camera_position)
        w.export_turbogrid_dialog()
        assert not warnings and '4 files exported' in w.statusBar().currentMessage()
        assert 'Shroud Tip: Profile Number 2' in w.statusBar().currentMessage()
        contours=read_profiles(case/'profile.curve')
        assert len(contours)==3
        expected,_=closed_profile(w.impeller_geometry.sections[-1])
        np.testing.assert_allclose(contours[-2],expected,rtol=6e-6,atol=6e-4)
        np.testing.assert_array_equal(w.impeller_geometry.sections[-1].master_ps.xyz,original)
        assert w.get_parameters()==before
        for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)
        saved={f.name:f.read_bytes() for f in case.iterdir()}
        e.controls['te_mm'].setValue(100.)
        w.export_turbogrid_dialog()
        assert warnings and {f.name:f.read_bytes() for f in case.iterdir()}==saved
    finally:
        for dialog in w._tool_dialogs.values():dialog.close()
        w.timer.stop();w.close();w.deleteLater();app.processEvents()
