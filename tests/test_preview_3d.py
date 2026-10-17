import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow


def test_camera_and_section_gui():
 app=QApplication.instance() or QApplication([])
 w=MainWindow();w.show();app.processEvents()
 w.preview_3d.camera_position['azimuth']=81
 w.preview_3d.camera_position['scale']=25
 w.preview_3d.camera_position['pan']=np.array([3.,4.])
 before=deepcopy(w.preview_3d.camera_position)
 preview_dialog=w.show_analysis_view("3D Preview");app.processEvents()
 # Opening the view now fits the model, while retaining its orientation.
 for key in ('azimuth','elevation','rotation'):
  np.testing.assert_allclose(w.preview_3d.camera_position[key],before[key])
 assert w.preview_3d.camera_position['scale']!=before['scale']
 before=deepcopy(w.preview_3d.camera_position)
 hub=w.impeller_geometry.sections[0].camber.xyz.copy()
 w.section_selector.combo.setCurrentIndex(1)
 w.angle_editor.table.cellWidget(1,1).setValue(30)
 w.update_geometry()
 np.testing.assert_allclose(w.impeller_geometry.sections[0].camber.xyz,hub)
 for key,value in before.items():np.testing.assert_allclose(w.preview_3d.camera_position[key],value)
 area_dialog=w.show_analysis_view("Flow Area");app.processEvents()
 w.meridional_editor.station_table.cellWidget(1,1).setValue(.18)
 w.update_geometry()
 preview_dialog.show();app.processEvents()
 for key in ('azimuth','elevation','rotation'):
  np.testing.assert_allclose(w.preview_3d.camera_position[key],before[key])
 assert w.get_parameters().sections[1].blade_angle.points[1].value==30
 w.copy_section(True)
 assert w.get_parameters().sections[1].blade_angle==w.get_parameters().sections[0].blade_angle
 copied_hub=deepcopy(w.get_parameters().sections[0].blade_angle)
 w.angle_editor.table.cellWidget(1,1).setValue(35)
 assert w.get_parameters().sections[0].blade_angle==copied_hub
 assert w.get_parameters().sections[1].blade_angle!=copied_hub
 w.add_span_section(.5);assert [s.span for s in w.get_parameters().sections]==[0,.5,1]
 w.delete_span_section();assert [s.span for s in w.get_parameters().sections]==[0,1]
 w.delete_span_section();assert len(w.get_parameters().sections)==2
 preview_dialog.close();area_dialog.close();w.close();w.timer.stop()


def test_gui_turbogrid_export_uses_current_tip_and_save_load(tmp_path,monkeypatch):
 from PySide6.QtWidgets import QFileDialog
 from blade_designer.fileio.project_io import load_project
 app=QApplication.instance() or QApplication([])
 w=MainWindow();w.section_selector.combo.setCurrentIndex(1)
 w.thickness_editor.table.cellWidget(1,1).setValue(6)
 w.save_to_path(tmp_path/'project.json')
 p=load_project(tmp_path/'project.json')
 assert p.sections[0].thickness.points[1].value==4
 assert p.sections[1].thickness.points[1].value==6
 case=tmp_path/'case'
 monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(case))
 w.export_turbogrid_dialog()
 assert all((case/name).exists() for name in ('hub.curve','shroud.curve','profile.curve','BladeGen.inf'))
 assert '4 files exported' in w.statusBar().currentMessage()
 w.new_project();w.load_from_path(tmp_path/'project.json')
 w.section_selector.combo.setCurrentIndex(1)
 assert w.thickness_editor.get_points()[1].value==6
 w.timer.stop();w.close()
