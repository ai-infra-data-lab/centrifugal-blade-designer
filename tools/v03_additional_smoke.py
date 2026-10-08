"""Reproducible additional-requirements QA; never modifies source user projects."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import sys,json,hashlib
from copy import deepcopy
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import BladeParameters,BladeSection,RotationDirection
from blade_designer.models.blade_edge import BladeEdgePosition
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid
from blade_designer.geometry.geometry_3d import generate_impeller

def main():
    app=QApplication.instance() or QApplication([])
    font=Path("C:/Windows/Fonts/segoeui.ttf")
    if not QFontDatabase.families() and font.exists():
        QFontDatabase.addApplicationFont(str(font));app.setFont(QFont("Segoe UI",9))
    app.setStyle("Fusion")
    out=ROOT/"artifacts/v0.3-additional";out.mkdir(parents=True,exist_ok=True)
    originals={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"blade.json",ROOT/"blade.csv") if p.exists()}
    w=MainWindow();w.resize(1440,1060);w.show();app.processEvents();w.fit_view();app.processEvents()
    report={"gui_size":[w.width(),w.height()],"blade_width":w.blade_plot.width(),"editor_width":w.tabs.width()}
    def screenshot(name):
        app.processEvents();assert w.grab().save(str(out/(name+".png")))
    screenshot("default")
    before=deepcopy(w.get_parameters());original=w.impeller_geometry.sections[0].camber.xyz.copy()
    rotation_view=np.array(w.blade_plot.getViewBox().viewRange())
    w.reverse_rotation();assert w.get_parameters().rotation_direction is RotationDirection.CW
    reflected=w.impeller_geometry.sections[0].camber.xyz
    np.testing.assert_allclose(reflected,original*[1,-1,1],atol=1e-12)
    np.testing.assert_allclose(w.blade_plot.getViewBox().viewRange(),rotation_view)
    # Explicit Fit View for the screenshot after verifying automatic preservation.
    w.fit_view();screenshot("cw_rotation")
    w.undo();assert w.get_parameters()==before
    w.redo();assert w.get_parameters().rotation_direction is RotationDirection.CW
    w.undo()
    report["reverse_rotation_undo_redo"]="PASS"
    report["rotation_preserves_view_before_explicit_fit"]="PASS"
    export_turbogrid(out/"default_ccw_case",w.get_parameters())
    p=w.get_parameters()
    p.impeller_edges.leading_edge=BladeEdgePosition(.2,.28)
    p.impeller_edges.trailing_edge=BladeEdgePosition(.72,.82)
    p.diffuser_edges.leading_edge=BladeEdgePosition(.88,.91)
    p.diffuser_edges.trailing_edge=BladeEdgePosition(.96,.97)
    hub=deepcopy(p.sections[0])
    p.sections=[]
    for span in (0,.25,.5,.75,1):
        section=deepcopy(hub);section.span=span
        section.blade_angle.points[1].value=62-22*span
        section.thickness.points[1].value=4+2*span
        p.sections.append(section)
    w.set_parameters(p);w.update_geometry();w.fit_view();app.processEvents()
    w.tabs.setCurrentIndex(3);w.tabs.widget(3).ensureWidgetVisible(w.meridional_editor.blade_edges)
    w.context_tabs.setCurrentIndex(0);screenshot("independent_edges")
    w.context_tabs.setCurrentIndex(3);w.vertical_splitter.setSizes([440,450]);app.processEvents();w.preview_3d.fit_view()
    screenshot("five_span_wireframe")
    assert len(w.preview_3d.spanwise_lines)==244
    assert all(len(line.xyz)==5 for line in w.preview_3d.spanwise_lines)
    report["spanwise_correspondence"]={"lines":244,"sections":5,"segments":["LE","PS","TE","SS"]}
    camera=deepcopy(w.preview_3d.camera_position)
    ranges=np.array(w.blade_plot.getViewBox().viewRange())
    box=w.meridional_editor.blade_edges.controls["impeller_edges","leading_edge","hub"]
    box.setValue(.22);box.editingFinished.emit();w.update_geometry()
    for key,value in camera.items():np.testing.assert_array_equal(w.preview_3d.camera_position[key],value)
    np.testing.assert_allclose(w.blade_plot.getViewBox().viewRange(),ranges)
    report["edge_edit_camera_and_view"]="PASS"
    save_project(out/"five_span_v03.json",w.get_parameters())
    assert load_project(out/"five_span_v03.json")==w.get_parameters()
    export_turbogrid(out/"five_span_ccw_case",w.get_parameters())
    w.reverse_rotation();export_turbogrid(out/"five_span_cw_case",w.get_parameters())
    screenshot("five_span_cw_wireframe")
    report["save_load_and_four_file_exports"]="PASS"
    for name,reference in (("old_v03_flow_path","old_v03_profiles"),("flow_path_before_additional","flow_path_before_additional")):
        g=generate_impeller(load_project(ROOT/"tests/fixtures"/(name+".json")))
        maximum=0.
        with np.load(ROOT/"tests/fixtures"/(reference+".npz")) as expected:
            for i,section in enumerate(g.sections):
                for curve in ("camber","master_ps","master_ss","master_le","master_te"):
                    maximum=max(maximum,float(np.max(np.abs(getattr(section,curve).xyz-expected[f"{i}_{curve}"]))))
        assert maximum<3e-6
        report[name+"_maximum_coordinate_delta_mm"]=maximum
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in originals.items())
    report.update({"result":"PASS","user_json_csv_unchanged":True,
        "rendering":"Qt offscreen, screenshots require visual review",
        "native_manual_gui":"NOT RUN","turbogrid_manual_import":"NOT RUN - no installation found"})
    (out/"smoke_result.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    w.timer.stop();w.close();print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
