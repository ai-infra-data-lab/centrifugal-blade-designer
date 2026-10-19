import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
import csv
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from blade_designer.gui.coordinate_export_dialog import CoordinateExportDialog
from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions
from blade_designer.geometry.row_domain import preview_wall_chunks
from test_coordinate_csv_gui import window  # shared project-window fixture


def test_wall_controls_combination_span_interlock_and_txt(monkeypatch):
    app = QApplication.instance() or QApplication([])
    d = CoordinateExportDialog()
    try:
        d.split.setChecked(True)
        d.hub.setChecked(True)
        assert not d.split.isEnabled() and not d.split.isChecked()
        d.shroud.setChecked(True)
        d.wall_layout.setCurrentIndex(2)
        assert d.split.isEnabled()
        d.split.setChecked(True)
        d.extension.setCurrentIndex(1)
        assert d.options().extension == 'txt' and d.options().requires_directory
        d.blades.setChecked(False)
        assert not d.split.isEnabled() and not d.split.isChecked()
        assert d.options() == CoordinateCsvOptions(include_blades=False, include_hub=True,
                                                   include_shroud=True, wall_layout='separate', extension='txt')
        d.hub.setChecked(False)
        d.shroud.setChecked(False)
        messages = []
        monkeypatch.setattr(QMessageBox, 'warning', lambda *args: messages.append(args[-1]))
        d.accept()
        assert messages and d.result() != QDialog.DialogCode.Accepted
    finally:
        d.close()
        d.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('identifier', ['row-1', 'row-2', 'row-3'])
@pytest.mark.parametrize('layout', ['combined', 'separate'])
def test_selected_walls_match_owned_preview_meridians_in_txt(window, identifier, layout, tmp_path):
    w = window
    w.select_blade_row(identifier)
    params = deepcopy(w.get_parameters())
    camera = deepcopy(w.model_preview_3d.camera_position)
    history = w.undo_stack.count()
    g = w.impeller_geometry if identifier == 'row-1' else w.diffuser_geometry
    chunks = preview_wall_chunks(params, g, identifier)
    options = CoordinateCsvOptions(('z_mm', 'r_mm', 'theta_rad'), include_blades=False,
                                   include_hub=True, include_shroud=True, wall_layout=layout, extension='txt')
    target = tmp_path / ('bundle' if options.requires_directory else 'walls.txt')
    files = w.export_coordinate_to_path(target, options)
    assert len(files) == (1 if layout == 'combined' else 2)
    rows = []
    for file in files:
        assert file.suffix == '.txt'
        with file.open(encoding='utf-8-sig', newline='') as stream:
            rows.extend(csv.DictReader(stream, delimiter='\t'))
    for wall in ('hub', 'shroud'):
        actual = [row for row in rows if row['blade_set'] == wall]
        expected = [[format(float(v), f'.{params.export.significant_digits}g') for v in (z, r, 0.)]
                    for chunk in chunks[wall] for r, z in zip(chunk.r, chunk.z)]
        assert [[row[k] for k in options.columns] for row in actual] == expected
        assert all(row['row_id'] == identifier for row in actual)
    assert w.get_parameters() == params and w.undo_stack.count() == history
    assert 'Coordinate TXT' in w.statusBar().currentMessage()
    for key, value in camera.items():
        np.testing.assert_array_equal(w.model_preview_3d.camera_position[key], value)


def test_txt_save_filter_extension_and_split_folder(window, tmp_path, monkeypatch):
    w = window
    options = CoordinateCsvOptions(include_blades=False, include_hub=True, include_shroud=True,
                                   wall_layout='separate', extension='txt')
    monkeypatch.setattr(CoordinateExportDialog, 'exec', lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(CoordinateExportDialog, 'options', lambda self: options)
    calls = []
    def select(*args):
        calls.append(args)
        return str(tmp_path / 'wall_model.csv'), 'TXT (*.txt)'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', select)
    w.export_coordinate_dialog()
    assert calls[0][-2:] == ('coordinates.txt', 'TXT (*.txt)')
    assert {p.name for p in (tmp_path / 'wall_model_files').iterdir()} == {'hub.txt', 'shroud.txt'}
    assert not (tmp_path / 'wall_model.csv').exists()
