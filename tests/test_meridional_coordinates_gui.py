"""Read-only segment coordinates use analytic primitives and follow GUI edits."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import json
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QAbstractItemView
from PySide6.QtTest import QTest
from blade_designer.gui.meridional_editor import MeridionalEditor
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.meridional import MeridionalCurveParameters,ArcSegmentParameters,LineSegmentParameters
from blade_designer.geometry.meridional_segments import generate_meridional


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def values(editor):
    return [[editor.coordinate_table.item(i,j).text() for j in (1,2)] for i in range(3)]


def assert_current_coordinates(editor):
    index=editor.selector.currentIndex();row=editor.table.currentRow()
    segment=generate_meridional(editor.get_curves()[index]).segments[row]
    for i,point in enumerate((segment.start,getattr(segment,'center',None),segment.end)):
        if point is None:assert values(editor)[i]==['—','—']
        else:np.testing.assert_allclose(np.array(values(editor)[i],dtype=float),[point.r,point.z],rtol=1e-11,atol=1e-10)


@pytest.mark.parametrize('clockwise',[False,True])
def test_arc_coordinates_are_analytic_r_z_and_selection_is_read_only(app,clockwise):
    editor=MeridionalEditor();editor.show();app.processEvents()
    try:
        hub=MeridionalCurveParameters(10,80,0,[ArcSegmentParameters(12,90,clockwise)])
        casing=MeridionalCurveParameters(10,150,0,[LineSegmentParameters(100)])
        editor.set_curves(hub,casing);before=editor.get_curves();changes=[]
        editor.parametersChanged.connect(lambda:changes.append(True))
        QTest.mouseClick(editor.table.cellWidget(0,2),Qt.MouseButton.LeftButton);app.processEvents()
        offset=-12 if clockwise else 12
        np.testing.assert_allclose(np.array(values(editor),dtype=float),[[80,10],[80+offset,10],[80+offset,22]],atol=1e-11)
        assert editor.get_curves()==before and changes==[]
        assert editor.coordinate_table.editTriggers()==QAbstractItemView.EditTrigger.NoEditTriggers
        assert all(not editor.coordinate_table.item(i,j).flags() & Qt.ItemFlag.ItemIsEditable for i in range(3) for j in range(3))
        assert 'Hub' in editor.coordinate_title.text() and 'Arc' in editor.coordinate_title.text()
        assert 'R =' in editor.coordinate_table.item(1,1).toolTip()
        editor.selector.setCurrentIndex(1);editor.table.selectRow(0)
        assert values(editor)==[['150','10'],['—','—'],['150','110']]
        assert 'Shroud' in editor.coordinate_title.text() and 'Line' in editor.coordinate_title.text()
        assert editor.get_curves()==before and changes==[]
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_coordinates_wait_for_input_commit_and_update_after_upstream_edit(app):
    editor=MeridionalEditor();editor.show();app.processEvents()
    try:
        editor.table.selectRow(1);before=values(editor);changes=[]
        editor.parametersChanged.connect(lambda:changes.append(True))
        box=editor.table.cellWidget(1,2);box.setFocus();box.selectAll()
        QTest.keyClicks(box,'31');app.processEvents()
        assert values(editor)==before and changes==[]
        editor.selector.setFocus();app.processEvents()
        assert len(changes)==1 and values(editor)!=before
        assert_current_coordinates(editor)
        # A preceding line moves all three points of this downstream arc.
        old=np.array(values(editor),dtype=float)
        editor.table.cellWidget(0,1).setValue(28)
        editor.table.selectRow(1)
        new=np.array(values(editor),dtype=float)
        np.testing.assert_allclose(new-old,[[0,3]]*3,atol=1e-10)
        assert_current_coordinates(editor)
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_coordinates_follow_type_add_move_delete_and_invalid_shape(app):
    editor=MeridionalEditor();editor.show();app.processEvents()
    try:
        editor.table.selectRow(1);assert_current_coordinates(editor)
        editor.table.cellWidget(1,0).setCurrentIndex(0)
        assert values(editor)[1]==['—','—'];assert_current_coordinates(editor)
        editor.table.cellWidget(1,0).setCurrentIndex(1);assert_current_coordinates(editor)
        editor.add_segment(True);assert_current_coordinates(editor)
        editor.move_segment(-1);assert_current_coordinates(editor)
        editor.delete_segment();editor.table.selectRow(1);assert_current_coordinates(editor)
        good=editor.get_curves();bad=deepcopy(good[0]);bad.segments[0].length=-1
        editor.set_curves(bad,good[1]);editor.table.selectRow(0)
        assert 'ERROR' in editor.message.text() and values(editor)==[['—','—']]*3
        editor.set_curves(*good);editor.table.selectRow(1);assert_current_coordinates(editor)
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_display_precision_preserves_model_and_fits_coordinate_text(app):
    editor=MeridionalEditor();editor.show();app.processEvents()
    try:
        curves=editor.get_curves();curves[0].segments[1].radius=30.12345678901234
        editor.set_curves(*curves);editor.table.selectRow(1);app.processEvents()
        assert editor.get_curves()==curves
        assert_current_coordinates(editor)
        item=editor.coordinate_table.item(1,1)
        assert len(item.text())>10
        assert editor.coordinate_table.columnWidth(1)>=editor.coordinate_table.fontMetrics().horizontalAdvance(item.text())
        assert item.toolTip()==f'R = {80.12345678901234:.17g} mm'
    finally:editor.close();editor.deleteLater();app.processEvents()


def test_coordinates_follow_undo_redo_and_json_without_saving_derived_points(app,tmp_path):
    w=MainWindow();w.show();app.processEvents()
    try:
        w._select_meridional();editor=w.meridional_editor;editor.table.selectRow(1)
        before=deepcopy(w.get_parameters());history=w.undo_stack.count();old=values(editor)
        assert_current_coordinates(editor)
        # Selecting rows and walls does not create an edit or change the model.
        editor.selector.setCurrentIndex(1);editor.table.selectRow(1)
        assert_current_coordinates(editor)
        editor.selector.setCurrentIndex(0);editor.table.selectRow(1)
        assert w.get_parameters()==before and w.undo_stack.count()==history
        box=editor.table.cellWidget(0,1);box.setFocus();box.selectAll();QTest.keyClicks(box,'28')
        editor.selector.setFocus();app.processEvents();w.timer.stop();w.update_geometry()
        editor.table.selectRow(1);assert_current_coordinates(editor)
        assert values(editor)!=old and w.undo_stack.count()==history+1
        after=deepcopy(w.get_parameters());w.undo();editor.table.selectRow(1)
        assert w.get_parameters()==before and values(editor)==old
        w.redo();editor.table.selectRow(1);assert_current_coordinates(editor)
        assert w.get_parameters()==after
        path=tmp_path/'coordinates.json';w.save_to_path(path);w.load_from_path(path)
        editor.table.selectRow(1);assert_current_coordinates(editor)
        assert w.get_parameters()==after
        data=json.loads(path.read_text(encoding='utf-8'))
        assert set(data['hub'])=={'start_z','start_r','start_angle_deg','segments','export_points'}
        assert all('center' not in segment and 'start' not in segment and 'end' not in segment for segment in data['hub']['segments'])
    finally:
        for dialog in w._tool_dialogs.values():dialog.close()
        w.timer.stop();w.close();w.deleteLater();app.processEvents()
