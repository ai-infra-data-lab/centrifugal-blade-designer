import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import numpy as np
import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import BladeParameters, EdgeType
from blade_designer.fileio.project_io import save_project, load_project


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); QTest.qWait(30)
    yield w
    w.timer.stop(); w.close(); w.deleteLater(); app.processEvents()


def test_shared_edge_edits_from_tip_preserve_distributions_and_undo(window, tmp_path):
    w = window; w.add_span_section(.5); w.select_section(2)
    before = deepcopy(w.get_parameters())
    le = w.panel.controls["le_type"]
    le.setCurrentIndex(le.findData(EdgeType.ELLIPTICAL))
    ratio = w.panel.controls["le_ellipse_ratio"]
    ratio.setValue(1.6); ratio.editingFinished.emit()
    te = w.panel.controls["te_type"]
    te.setCurrentIndex(te.findData(EdgeType.CUTOFF))
    w.update_geometry(); after = deepcopy(w.get_parameters())
    assert all(s.edge_parameters == after.sections[0].edge_parameters for s in after.sections)
    assert all(s.edge_parameters.le_type == EdgeType.ELLIPTICAL and
               s.edge_parameters.le_ellipse_ratio == 1.6 and
               s.edge_parameters.te_type == EdgeType.CUTOFF for s in after.sections)
    for old, new in zip(before.sections, after.sections):
        assert old.blade_angle == new.blade_angle and old.thickness == new.thickness
    assert after.diffuser_profile == before.diffuser_profile
    w.undo(); assert all(s.edge_parameters.te_type == EdgeType.CIRCULAR for s in w.get_parameters().sections)
    w.redo(); assert w.get_parameters() == after
    w.save_to_path(tmp_path / "shared.json"); w.new_project(); w.load_from_path(tmp_path / "shared.json")
    assert w.get_parameters() == after
    assert all(s.edge_parameters == after.sections[0].edge_parameters for s in load_project(tmp_path / "shared.json").sections)


def test_old_independent_edge_project_uses_hub_shape_without_modifying_file(window, tmp_path):
    p = BladeParameters()
    p.sections[0].edge_parameters.le_type = EdgeType.ELLIPTICAL
    p.sections[0].edge_parameters.le_ellipse_ratio = 1.2
    p.sections[1].edge_parameters.te_type = EdgeType.CUTOFF
    p.diffuser_profile.edge_parameters.le_type = EdgeType.CUTOFF
    path = tmp_path / "old.json"; save_project(path, p); original = path.read_bytes()
    window.load_from_path(path)
    current = window.get_parameters()
    assert path.read_bytes() == original
    assert all(s.edge_parameters == p.sections[0].edge_parameters for s in current.sections)
    assert current.diffuser_profile == p.diffuser_profile
    expected = window.designer.generate_3d(current)
    np.testing.assert_array_equal(window.impeller_geometry.sections[1].master_te.xyz,
                                  expected.sections[1].master_te.xyz)


def test_diffuser_curvature_hidden_and_diffuser_edges_remain_independent(window):
    w = window; index = w.tabs.indexOf(w.curvature_plot)
    assert not w.tabs.isTabVisible(index)
    original = deepcopy(w.get_parameters().sections)
    w.view_mode.setCurrentIndex(1)
    assert not w.tabs.isTabVisible(index)
    dialog = w.show_analysis_view("Diffuser Curvature")
    assert w.curvature_plot.isVisible()
    combo = w.panel.controls["te_type"]
    combo.setCurrentIndex(combo.findData(EdgeType.CUTOFF)); w.update_geometry()
    assert w.get_parameters().sections == original
    assert w.get_parameters().diffuser_profile.edge_parameters.te_type == EdgeType.CUTOFF
    w.view_mode.setCurrentIndex(0)
    assert all(w.tabs.tabText(i) != "Diffuser Curvature" for i in range(w.tabs.count()) if w.tabs.isTabVisible(i))
    dialog.close()


@pytest.mark.parametrize("plane", ["XY", "XZ", "YZ"])
@pytest.mark.parametrize("section_index", [0, 1])
def test_annulus_rotates_selected_impeller_in_xyz_before_projection(window, plane, section_index):
    w = window; w.panel.controls["vane_count"].setValue(3)
    w.select_section(section_index); w.projection.setCurrentText(plane); w.update_geometry()
    section = w.impeller_geometry.sections[section_index]
    for name, curve in w.annulus_plot.curves.items():
        source = getattr(section, "master_" + name.lower())
        block_size = len(source.x) + 1
        x, y = curve.getData()
        assert len(x) == 3 * block_size
        for blade_index in range(3):
            angle = 2*np.pi*blade_index/3
            coordinates = {"X": source.x*np.cos(angle)-source.y*np.sin(angle),
                           "Y": source.x*np.sin(angle)+source.y*np.cos(angle), "Z": source.z}
            block = slice(blade_index*block_size, (blade_index+1)*block_size-1)
            np.testing.assert_allclose(x[block], coordinates[plane[0]], atol=1e-12)
            np.testing.assert_allclose(y[block], coordinates[plane[1]], atol=1e-12)
            assert np.isnan(x[(blade_index+1)*block_size-1])
    assert ("Hub" if section_index == 0 else "Tip") in w.annulus_plot.plotItem.titleLabel.text
    assert w.annulus_plot.throat_line.xData is None or len(w.annulus_plot.throat_line.xData) == 0
    view = w.annulus_plot.getViewBox(); view.setRange(xRange=(-50, 50), yRange=(-60, 60), padding=0)
    ranges = np.array(view.viewRange())
    w.angle_editor.series[section.span].table.cellWidget(1, 1).setValue(43); w.update_geometry()
    np.testing.assert_allclose(view.viewRange(), ranges)
    w.view_mode.setCurrentIndex(1)
    source = w.diffuser_geometry.sections[0].master_ps; x, y = w.annulus_plot.curves["PS"].getData()
    np.testing.assert_array_equal(x[:len(source.x)], source.x)
    np.testing.assert_array_equal(y[:len(source.y)], source.y)
    assert "Diffuser" in w.annulus_plot.plotItem.titleLabel.text


@pytest.mark.parametrize("hub_to_tip", [True, False])
def test_copy_api_only_copies_distributions_and_buttons_removed(window, hub_to_tip):
    w = window
    w.angle_editor.series[0].table.cellWidget(1, 1).setValue(41)
    w.angle_editor.series[1].table.cellWidget(1, 1).setValue(35)
    w.thickness_editor.series[0].table.cellWidget(1, 1).setValue(5)
    w.thickness_editor.series[1].table.cellWidget(1, 1).setValue(6)
    w.commit_edit(); before = deepcopy(w.get_parameters())
    assert not any("Copy" in b.text() for b in w.section_selector.findChildren(QPushButton))
    w.copy_section(hub_to_tip); after = w.get_parameters()
    source, target = (0, 1) if hub_to_tip else (1, 0)
    assert after.sections[target].blade_angle == before.sections[source].blade_angle
    assert after.sections[target].thickness == before.sections[source].thickness
    assert after.sections[source] == before.sections[source]
    assert after.sections[target].span == before.sections[target].span
    assert after.sections[target].edge_parameters == before.sections[target].edge_parameters
    assert after.diffuser_profile == before.diffuser_profile
    w.undo(); assert w.get_parameters() == before
    w.redo(); assert w.get_parameters() == after
