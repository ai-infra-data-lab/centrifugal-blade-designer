import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from blade_designer.gui.main_window import MainWindow
from blade_designer.geometry.geometry_3d import generate_diffuser_3d
from blade_designer.models.blade_rows import row_parameters
from test_stator_turbogrid_export import stator_project, profiles


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    yield w
    w.timer.stop();w.close();w.deleteLater();app.processEvents()


def export_to(window,directory,monkeypatch):
    warnings=[]
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(directory))
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:warnings.append(args[-1]))
    window.export_turbogrid_dialog()
    return warnings


@pytest.mark.parametrize('identifier',['row-2','row-3'])
def test_selected_stator_dialog_exports_current_geometry_and_annulus_is_display_only(window,tmp_path,monkeypatch,identifier):
    w=window;project=stator_project(identifier)
    selected=next(row for row in project.blade_rows if row.identifier==identifier)
    p=row_parameters(project,selected);p.blade_rows=deepcopy(project.blade_rows);p.active_blade_row=identifier
    w.set_parameters(p);w._reset_history();w.update_geometry()
    # A pending distribution change is committed by Export, even before the update timer fires.
    box=w.angle_editor.table.cellWidget(1,1)
    box.setValue(box.value()+2)
    case=tmp_path/'case'
    assert export_to(w,case,monkeypatch)==[]
    w.update_geometry()
    params=w.get_parameters();g=generate_diffuser_3d(params)
    for (_,actual,_),s,display in zip(profiles(case/'profile.curve'),g.sections,w.diffuser_geometry.sections):
        expected=np.concatenate([s.le.xyz[:-1],s.ps.xyz[:-1],s.te.xyz[:-1],s.ss.xyz[::-1][:-1],s.le.xyz[:1]])
        np.testing.assert_allclose(actual,expected,atol=1e-12)
        np.testing.assert_array_equal(s.master_ps.xyz,display.master_ps.xyz)
    np.testing.assert_array_equal(w.model_preview_3d.base_lines['Hub ps'][0],g.sections[0].master_ps.xyz)
    for name in ('Hub','Shroud'):
        np.testing.assert_allclose(np.loadtxt(case/(name.lower()+'.curve'))[[0,-1]],
            w.model_preview_3d.base_lines[name][0][[0,-1]],atol=1e-12)
    before={f.name:f.read_bytes() for f in case.iterdir()}
    w.annulus_3d.setChecked(True)
    assert export_to(w,case,monkeypatch)==[]
    assert {f.name:f.read_bytes() for f in case.iterdir()}==before
    assert w.get_parameters()==params


def test_meridional_selection_rejected_before_directory_dialog(window,monkeypatch):
    w=window;w._select_meridional();warnings=[]
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:warnings.append(args[-1]))
    def unexpected(*args):raise AssertionError('No export directory should be requested')
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',unexpected)
    w.export_turbogrid_dialog()
    assert warnings==['Select a blade row for TurboGrid export.']


def test_invalid_current_stator_does_not_export_last_valid_preview(window,tmp_path,monkeypatch):
    w=window;w.select_blade_row('row-2');w.update_geometry()
    case=tmp_path/'case'
    assert export_to(w,case,monkeypatch)==[]
    before={f.name:f.read_bytes() for f in case.iterdir()}
    previous=w.diffuser_geometry
    box=w.meridional_editor.blade_edges.row_controls['row-2','trailing_edge','hub']
    box.setValue(.1)
    w.update_geometry()
    assert w.diffuser_geometry is previous
    warnings=export_to(w,case,monkeypatch)
    assert warnings
    assert {f.name:f.read_bytes() for f in case.iterdir()}==before


def test_cancel_static_export_does_not_change_parameters(window,monkeypatch):
    window.select_blade_row('row-2');before=deepcopy(window.get_parameters())
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:'')
    window.export_turbogrid_dialog()
    assert window.get_parameters()==before
