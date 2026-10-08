"""Render target-specific editors and verify independent optimization window."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys, json, hashlib
from pathlib import Path
from copy import deepcopy
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from blade_designer.gui.main_window import MainWindow
from blade_designer.fileio.project_io import load_project


def main():
    app = QApplication.instance() or QApplication([])
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if not QFontDatabase.families() and font.exists():
        QFontDatabase.addApplicationFont(str(font)); app.setFont(QFont("Segoe UI", 9))
    app.setStyle("Fusion")
    output = ROOT / "artifacts/simultaneous-editors"; output.mkdir(exist_ok=True)
    originals = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (ROOT / "blade.json", ROOT / "blade.csv") if p.exists()}
    w = MainWindow(); w.resize(1600, 1100); w.show(); app.processEvents()
    for name, values in (("angle_editor", (46, 38)), ("thickness_editor", (5, 6))):
        editor = getattr(w, name)
        for span, value in enumerate(values):
            box = editor.series[span].table.cellWidget(1, 1)
            box.setValue(value); box.editingFinished.emit()
        w.tabs.setCurrentWidget(editor); w.update_geometry(); w.fit_view(); app.processEvents()
        assert all(e.table.isVisible() for e in editor.series.values())
        assert w.grab().save(str(output / f"impeller_{name}.png"))
    assert w.section_selector.combo.currentIndex() == 0
    before = deepcopy(w.get_parameters())
    w.save_to_path(output / "hub_tip.json"); assert load_project(output / "hub_tip.json") == before
    w.view_mode.setCurrentIndex(1); w.tabs.setCurrentIndex(0); w.fit_view(); app.processEvents()
    assert w.grab().save(str(output / "diffuser_angle.png"))
    w.tabs.setCurrentIndex(4); app.processEvents()
    assert w.grab().save(str(output / "diffuser_output.png"))
    other = w.open_optimization_mode(); other.resize(1600, 1100); app.processEvents()
    assert other.grab().save(str(output / "optimization_mode.png"))
    row = next(row for row in other.optimization_widget.rows if row["parameter"].name == "beta_te")
    row["initial"].setValue(-1); other.optimization_widget.preview_candidate()
    assert other.optimization_widget.last_result.feasible
    other.optimization_widget.apply_candidate()
    assert w.get_parameters() == before
    assert other.get_parameters().diffuser_profile.blade_angle.points[-1].value == 49
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in originals.items())
    (output / "result.json").write_text(json.dumps({
        "result": "PASS", "simultaneous_hub_tip_tables": "PASS", "project_roundtrip": "PASS",
        "optimization_window_isolation": "PASS", "original_json_csv_unchanged": True,
        "rendering": "Qt offscreen", "native_manual_gui": "NOT RUN"
    }, indent=2) + "\n", encoding="utf-8")
    other.timer.stop(); other.close(); w.timer.stop(); w.close(); app.processEvents()
    print("PASS: simultaneous Hub/Tip editors, target controls, independent optimization, project roundtrip")


if __name__ == "__main__":
    main()
