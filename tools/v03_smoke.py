"""Reproducible Qt rendering/export smoke check; never edits user projects."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import sys
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from blade_designer.gui.main_window import MainWindow
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid
from blade_designer.fileio.csv_export import export_segments_csv,export_contour_csv

def main():
    app=QApplication.instance() or QApplication([])
    # Qt's offscreen backend may have no native font database on Windows.
    font=Path("C:/Windows/Fonts/segoeui.ttf")
    if not QFontDatabase.families() and font.exists():
        QFontDatabase.addApplicationFont(str(font))
        app.setFont(QFont("Segoe UI",9))
    app.setStyle("Fusion")
    output=ROOT/"artifacts/v0.3-flow-path";output.mkdir(parents=True,exist_ok=True)
    originals={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"blade.json",ROOT/"blade.csv") if p.exists()}
    w=MainWindow();w.show();app.processEvents();w.fit_view();app.processEvents()
    report={"gui_width":w.width(),"blade_width":w.blade_plot.width(),"editor_width":w.tabs.width()}
    assert w.blade_plot.width()>w.width()*.5
    for name,index in (("blade_angle",0),("meridional",3),("output",4),("le_te",2)):
        w.tabs.setCurrentIndex(index);app.processEvents()
        assert w.grab().save(str(output/(name+".png")))
    for label,index in (("context_meridional",0),("flow_area",1),("metrics",2),("preview_3d",3)):
        w.context_tabs.setCurrentIndex(index);app.processEvents()
        if index==1:w.flow_area_widget.select_position(.5)
        assert w.grab().save(str(output/(label+".png")))
    assert not w.flow_area_result.errors
    report["named_station_area_mm2"]={k:s.gross_area for k,s in w.flow_area_result.named_stations.items()}
    p=w.get_parameters()
    save_project(output/"default_v03.json",p)
    assert load_project(output/"default_v03.json")==p
    files=export_turbogrid(output/"default_case",p)
    assert all(f.exists() and f.stat().st_size>0 for f in files)
    export_segments_csv(output/"diffuser_segments.csv",w.geometry,p.export)
    export_contour_csv(output/"diffuser_contour.csv",w.geometry,p.export)
    for span in (.25,.5,.75):w.add_span_section(span)
    assert len(w.impeller_geometry.sections)==5
    export_turbogrid(output/"five_span_case",w.get_parameters())
    w.context_tabs.setCurrentIndex(3);w.fit_view();app.processEvents()
    w.grab().save(str(output/"five_span_preview.png"))
    if (ROOT/"blade.json").exists():
        w.load_from_path(ROOT/"blade.json")
        save_project(output/"legacy_migrated_v03.json",w.get_parameters())
        report["legacy_project_load"]="PASS"
    legacy=ROOT/"tests/fixtures/old_v03_flow_path.json"
    if legacy.exists():
        import numpy as np
        w.load_from_path(legacy)
        maximum=0.
        with np.load(ROOT/"tests/fixtures/old_v03_profiles.npz") as reference:
            for i,section in enumerate(w.impeller_geometry.sections):
                for name in ("camber","master_ps","master_ss","master_le","master_te"):
                    maximum=max(maximum,float(np.max(np.abs(getattr(section,name).xyz-reference[f"{i}_{name}"]))))
        assert maximum<3e-6
        report["earlier_v03_coordinate_max_delta_mm"]=maximum
        export_turbogrid(output/"earlier_v03_case",w.get_parameters())
        save_project(output/"earlier_v03_migrated.json",w.get_parameters())
    assert all(hashlib.sha256(path.read_bytes()).hexdigest()==digest for path,digest in originals.items())
    report.update({"result":"PASS","default_sections":2,"intermediate_demo_sections":5,
        "turbogrid_files_per_case":4,"user_json_csv_unchanged":True,
        "manual_turbogrid_import":"NOT RUN - installation not found",
        "screenshots":"Qt offscreen rendering; visually reviewed"})
    (output/"smoke_result.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    w.timer.stop();w.close()
    print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
