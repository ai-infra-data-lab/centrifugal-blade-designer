"""Verify shared edge settings and render target-specific annulus previews."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys, json, hashlib
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import EdgeType
from blade_designer.fileio.project_io import load_project


def main():
    app = QApplication.instance() or QApplication([])
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if not QFontDatabase.families() and font.exists():
        QFontDatabase.addApplicationFont(str(font)); app.setFont(QFont("Segoe UI", 9))
    app.setStyle("Fusion")
    output = ROOT / "artifacts/shared-edges-annulus"; output.mkdir(exist_ok=True)
    originals = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (ROOT / "blade.json", ROOT / "blade.csv") if p.exists()}
    w = MainWindow(); w.resize(1600, 1100); w.show(); app.processEvents()
    w.section_selector.combo.setCurrentIndex(1)
    box = w.panel.controls["le_type"]; box.setCurrentIndex(box.findData(EdgeType.ELLIPTICAL))
    box = w.panel.controls["le_ellipse_ratio"]; box.setValue(1.3); box.editingFinished.emit()
    w.update_geometry(); p = w.get_parameters()
    assert all(s.edge_parameters == p.sections[0].edge_parameters for s in p.sections)
    assert p.diffuser_profile.edge_parameters.le_type == EdgeType.CIRCULAR
    w.save_to_path(output / "shared_edges.json"); assert load_project(output / "shared_edges.json") == p
    def capture(widget, filename):
        if widget is w.annulus_plot:
            w.annulus_2d.setChecked(True)
            w.tabs.setCurrentIndex(next(i for i in range(w.tabs.count()) if w.tabs.tabText(i) == "Full Annulus"))
        else:
            w.tabs.setCurrentWidget(widget)
        w.fit_view(); app.processEvents()
        assert w.grab().save(str(output / filename))
    w.tabs.setCurrentIndex(2); capture(w.tabs.currentWidget(), "impeller_shared_edges.png")
    assert not w.tabs.isTabVisible(w.tabs.indexOf(w.curvature_plot))
    w.section_selector.combo.setCurrentIndex(0); capture(w.annulus_plot, "impeller_annulus_hub_xy.png")
    w.section_selector.combo.setCurrentIndex(1); w.projection.setCurrentText("XZ")
    capture(w.annulus_plot, "impeller_annulus_tip_xz.png")
    w.view_mode.setCurrentIndex(1); capture(w.annulus_plot, "diffuser_annulus_xy.png")
    assert not w.tabs.isTabVisible(w.tabs.indexOf(w.curvature_plot))
    dialog = w.show_analysis_view("Diffuser Curvature"); app.processEvents()
    assert dialog.grab().save(str(output / "diffuser_curvature.png")); dialog.close()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in originals.items())
    (output / "result.json").write_text(json.dumps({
        "result": "PASS", "shared_impeller_edges": "PASS", "independent_diffuser_edges": "PASS",
        "curvature_visibility": "PASS", "target_annulus": "PASS", "project_roundtrip": "PASS",
        "original_json_csv_unchanged": True, "rendering": "Qt offscreen", "native_manual_gui": "NOT RUN"
    }, indent=2) + "\n", encoding="utf-8")
    w.timer.stop(); w.close(); app.processEvents()
    print("PASS: shared LE/TE, target annulus, curvature visibility, project roundtrip")


if __name__ == "__main__":
    main()
