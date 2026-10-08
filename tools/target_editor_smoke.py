"""Target-specific distribution and orthographic projection rendering QA."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import sys,json,hashlib,csv
from pathlib import Path
from copy import deepcopy
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from blade_designer.gui.main_window import MainWindow
from blade_designer.fileio.project_io import load_project

def main():
    app=QApplication.instance() or QApplication([])
    font=Path("C:/Windows/Fonts/segoeui.ttf")
    if not QFontDatabase.families() and font.exists():
        QFontDatabase.addApplicationFont(str(font));app.setFont(QFont("Segoe UI",9))
    app.setStyle("Fusion")
    output=ROOT/"artifacts/target-editors";output.mkdir(exist_ok=True)
    originals={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"blade.json",ROOT/"blade.csv") if p.exists()}
    w=MainWindow();w.resize(1440,1060);w.show();app.processEvents()
    for box,value in ((w.angle_editor.table.cellWidget(1,1),45),(w.thickness_editor.table.cellWidget(1,1),5)):
        box.setValue(value);box.editingFinished.emit()
    w.update_geometry();hub=w.impeller_geometry.sections[0].master_ps.xyz.copy()
    impeller=deepcopy(w.get_parameters().sections)
    views={}
    for plane in ("XY","XZ","YZ"):
        w.projection.setCurrentText(plane);w.fit_view();app.processEvents()
        x,y=w.blade_plot.camber_curve.getData();section=w.impeller_geometry.sections[0]
        np.testing.assert_array_equal(x,getattr(section.camber,plane[0].lower()))
        np.testing.assert_array_equal(y,getattr(section.camber,plane[1].lower()))
        assert w.grab().save(str(output/f"impeller_{plane.lower()}.png"))
        views[plane]=[float(np.ptp(x)),float(np.ptp(y))]
    w.view_mode.setCurrentIndex(1)
    assert not w.section_selector.isVisible() and not w.projection.isEnabled()
    for row,value in enumerate((60,55,50,45,40)):
        box=w.angle_editor.table.cellWidget(row,1);box.setValue(value);box.editingFinished.emit()
    box=w.thickness_editor.table.cellWidget(1,1);box.setValue(6);box.editingFinished.emit()
    w.update_geometry();w.fit_view();app.processEvents()
    assert w.get_parameters().sections==impeller
    np.testing.assert_array_equal(w.impeller_geometry.sections[0].master_ps.xyz,hub)
    assert w.grab().save(str(output/"diffuser_angle.png"))
    w.tabs.setCurrentIndex(1);app.processEvents()
    assert w.grab().save(str(output/"diffuser_thickness.png"))
    project=output/"separate_profiles.json";w.save_to_path(project)
    p=w.get_parameters();assert load_project(project)==p
    assert p.sections[0].blade_angle.points[1].value==45
    assert p.diffuser_profile.blade_angle.points[1].value==55
    assert p.sections[0].thickness.points[1].value==5
    assert p.diffuser_profile.thickness.points[1].value==6
    w.export_to_path(output/"diffuser_segments.csv")
    with (output/"diffuser_segments.csv").open() as stream:
        assert len(list(csv.DictReader(stream)))==244
    w.view_mode.setCurrentIndex(0)
    assert w.projection.currentText()=="YZ"
    assert w.angle_editor.get_points()[1].value==45
    w.new_project();w.load_from_path(project)
    assert w.get_parameters()==p
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in originals.items())
    report={"result":"PASS","projection_coordinate_spans_mm":views,
        "independent_impeller_diffuser_profiles":"PASS","project_roundtrip":"PASS","diffuser_csv":"PASS",
        "user_json_csv_unchanged":True,"rendering":"Qt offscreen; visual review pending","native_manual_gui":"NOT RUN"}
    (output/"smoke_result.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    w.timer.stop();w.close();print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
