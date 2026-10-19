import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
import csv
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from blade_designer.gui.coordinate_export_dialog import CoordinateExportDialog
from blade_designer.gui.main_window import MainWindow
from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions
from blade_designer.fileio.project_io import load_project
from test_row_xyz_csv import TEMPLATE
from test_standard_menus_gui import dispose


def test_presets_reorder_selection_and_empty_guard(monkeypatch):
    app = QApplication.instance() or QApplication([])
    d = CoordinateExportDialog()
    try:
        assert d.options() == CoordinateCsvOptions()
        d.preset.setCurrentIndex(2)
        assert d.options().columns == ('r_mm', 'theta_rad', 'z_mm')
        d.columns.setCurrentRow(2)
        d.up.click()
        assert d.options().columns == ('r_mm', 'z_mm', 'theta_rad')
        d.down.click()
        d.split.setChecked(True)
        d.metadata.setChecked(False)
        assert d.options() == CoordinateCsvOptions(('r_mm', 'theta_rad', 'z_mm'), True, False)
        for i in range(d.columns.count()):
            d.columns.item(i).setCheckState(Qt.CheckState.Unchecked)
        messages = []
        monkeypatch.setattr(QMessageBox, 'warning', lambda *args: messages.append(args[-1]))
        d.accept()
        assert messages and d.result() != QDialog.DialogCode.Accepted
        d.preset.setCurrentIndex(3)
        assert d.options().columns == ('rtheta_mm', 'z_mm', 'r_mm')
        d.accept()
        assert d.result() == QDialog.DialogCode.Accepted
    finally:
        d.close()
        d.deleteLater()
        app.processEvents()


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = MainWindow(default_parameters=load_project(TEMPLATE))
    w.timer.stop()
    yield w
    dispose(w, app)


@pytest.mark.parametrize('identifier', ['row-1', 'row-2', 'row-3'])
def test_selected_row_custom_output_matches_preview_and_preserves_design(window, identifier, tmp_path):
    w = window
    w.select_blade_row(identifier)
    p = deepcopy(w.get_parameters())
    history = w.undo_stack.count()
    camera = deepcopy(w.model_preview_3d.camera_position)
    g = w.impeller_geometry if identifier == 'row-1' else w.diffuser_geometry
    target = tmp_path / 'custom.csv'
    w.export_coordinate_to_path(target, CoordinateCsvOptions(('z_mm', 'rtheta_mm', 'r_mm')))
    with target.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    ps = [r for r in rows if r['blade_set'] == 'main' and r['span'] == '0' and r['segment'] == 'PS']
    c = g.sections[0].master_ps
    import numpy as np
    digits = p.export.significant_digits
    expected = [[format(float(value), f'.{digits}g') for value in xyz]
                for xyz in np.column_stack((c.z, c.r * c.theta_rad, c.r))]
    assert [[r[k] for k in ('z_mm', 'rtheta_mm', 'r_mm')] for r in ps] == expected
    assert {r['row_id'] for r in rows} == {identifier}
    assert w.get_parameters() == p and w.undo_stack.count() == history
    for key, value in camera.items():
        np.testing.assert_array_equal(w.model_preview_3d.camera_position[key], value)


def test_dialog_cancel_save_cancel_and_split_dispatch(window, tmp_path, monkeypatch):
    w = window
    before = deepcopy(w.get_parameters())
    paths = []
    monkeypatch.setattr(CoordinateExportDialog, 'exec', lambda self: QDialog.DialogCode.Rejected)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: paths.append('prompt') or ('', ''))
    w.export_coordinate_dialog()
    assert not paths
    monkeypatch.setattr(CoordinateExportDialog, 'exec', lambda self: QDialog.DialogCode.Accepted)
    w.export_coordinate_dialog()
    assert paths == ['prompt'] and not list(tmp_path.iterdir())
    monkeypatch.setattr(CoordinateExportDialog, 'options', lambda self: CoordinateCsvOptions(('r_mm', 'theta_rad', 'z_mm'), True))
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path / 'sample.csv'), 'CSV'))
    w.export_coordinate_dialog()
    assert len(list((tmp_path / 'sample_spans').glob('*.csv'))) == len(w.diffuser_geometry.sections)
    assert w.get_parameters() == before


def test_meridional_selection_refuses_export_without_opening_options(window, tmp_path, monkeypatch):
    w = window
    w._select_meridional()
    with pytest.raises(ValueError, match='Select a blade row'):
        w.export_coordinate_to_path(tmp_path / 'no.csv', CoordinateCsvOptions())
    monkeypatch.setattr(CoordinateExportDialog, 'exec', lambda self: pytest.fail('Unexpected options dialog'))
    messages = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: messages.append(args[-1]))
    w.export_coordinate_dialog()
    assert messages and not (tmp_path / 'no.csv').exists()
