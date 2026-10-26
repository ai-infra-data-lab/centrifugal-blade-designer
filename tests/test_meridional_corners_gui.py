import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QApplication
from blade_designer.gui.meridional_editor import MeridionalEditor
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.models.blade_rows import row_parameters
from blade_designer.geometry.meridional_segments import generate_meridional
from tests.test_meridional_elements_gui import window
from tests.test_gui import wait_for_geometry


def test_segment_join_input_commits_on_enter_and_conversion_keeps_angle():
    app=QApplication.instance() or QApplication([]);e=MeridionalEditor();e.show();app.processEvents()
    try:
        e.set_curves(*[MeridionalCurveParameters(0,r,0,[LineSegmentParameters(10),LineSegmentParameters(10)]) for r in (100,110)])
        control=e.table.cellWidget(1,7);control.mode.setCurrentIndex(1)
        spy=QSignalSpy(e.parametersChanged);control.angle.setFocus();control.angle.lineEdit().selectAll()
        QTest.keyClicks(control.angle.lineEdit(),'25');app.processEvents()
        assert spy.count()==0 and e.curves[0].segments[1].inlet_turn_deg==0.
        QTest.keyClick(control.angle.lineEdit(),Qt.Key.Key_Return);app.processEvents()
        assert spy.count()==1 and e.curves[0].segments[1].inlet_turn_deg==25.
        a,b=generate_meridional(e.curves[0]).segments
        np.testing.assert_array_equal(a.end.zr,b.start.zr)
        np.testing.assert_allclose(b.start_tangent,[np.cos(np.deg2rad(25)),np.sin(np.deg2rad(25))])
        assert 'G0' in e.message.text()
        e._type_changed(1,True)
        assert e.curves[0].segments[1].inlet_turn_deg==25.
        assert e.table.cellWidget(1,7).value()==25.
        e.table.selectRow(1);e.move_segment(-1)
        assert e.curves[0].segments[0].inlet_turn_deg==25.
        assert e.table.cellWidget(0,7).mode.itemText(0)=='開始方向'
    finally:e.close();e.deleteLater();app.processEvents()


def test_element_corner_widgets_history_save_and_parent_following(window,tmp_path):
    w=window;w.add_blade_row('meridional','Corner duct')
    identifier=w.get_parameters().active_blade_row
    assert not w.meridional_editor.table.cellWidget(0,7).isEnabled()
    control=w.element_walls_editor.joins['hub'];control.mode.setCurrentIndex(1);wait_for_geometry(w)
    before_angle=deepcopy(w.get_parameters())
    camera=deepcopy(w.model_preview_3d.camera_position)
    control=w.element_walls_editor.joins['hub'];control.angle.setValue(12);control.angle.editingFinished.emit();wait_for_geometry(w)
    p=w.get_parameters();row=p.blade_rows[-1]
    assert row.hub_inlet_turn_deg==12 and row.shroud_inlet_turn_deg is None
    assert row_parameters(p,row).hub.start_angle_deg==102.
    for key,value in camera.items():np.testing.assert_array_equal(w.model_preview_3d.camera_position[key],value)
    w.undo();assert w.get_parameters()==before_angle
    w.redo();assert w.get_parameters()==p
    path=tmp_path/'corner_element.json';w.save_to_path(path);w.load_from_path(path)
    assert w.get_parameters()==p and w.element_walls_editor.joins['hub'].value()==12
    original=row_parameters(p,p.blade_rows[-1]).hub.start_z
    w._select_meridional();w.meridional_editor.curves[0].start_z+=3;w.commit_edit();w.select_blade_row(identifier)
    changed=w.get_parameters();effective=row_parameters(changed,changed.blade_rows[-1])
    assert effective.hub.start_z==original+3
    assert changed.blade_rows[-1].hub_inlet_turn_deg==12
