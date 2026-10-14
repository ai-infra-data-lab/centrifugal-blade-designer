import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy

import numpy as np
import pytest
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent,QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from blade_designer.gui.preview_3d import Preview3D
from blade_designer.gui.main_window import MainWindow
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.models.parameters import BladeParameters


@pytest.fixture
def preview():
    app=QApplication.instance() or QApplication([])
    view=Preview3D();view.resize(600,400);view.show();app.processEvents()
    yield view
    view.close();view.deleteLater();app.processEvents()


def drag(view,start,end,button=Qt.MouseButton.LeftButton):
    QTest.mousePress(view,button,pos=start)
    event=QMouseEvent(QEvent.Type.MouseMove,QPointF(end),QPointF(view.mapToGlobal(end)),
                     Qt.MouseButton.NoButton,button,Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view,event)
    QTest.mouseRelease(view,button,pos=end)


def test_mouse_rotation_continues_past_pole_and_never_changes_geometry(preview):
    p=BladeParameters();g=generate_impeller(p);preview.update_geometry(g)
    before={name:xyz.copy() for name,(xyz,color) in preview.base_lines.items()}
    preview.camera_position.update(azimuth=0.,elevation=89.)
    start=QPoint(300,232);end=QPoint(300,89)
    directions=[]
    for _ in range(4):
        drag(preview,start,end)
        directions.append(preview._view_basis()[2].copy())
    assert directions[1][2]<-.9  # reached the opposite side, past the old +89 limit
    assert all(np.linalg.norm(a-b)>.5 for a,b in zip(directions,directions[1:]))
    for name,xyz in before.items():np.testing.assert_array_equal(preview.base_lines[name][0],xyz)
    assert preview._last is None


def test_trackball_roll_antipodal_points_and_long_drag_sequence_stay_orthonormal(preview):
    original=preview._view_basis().copy()
    preview._rotate_trackball(QPointF(445,232),QPointF(300,87))
    assert not np.allclose(preview._view_basis(),original)
    preview._rotate_trackball(QPointF(0,232),QPointF(600,232))
    for i in range(300):
        angle=i*.1
        preview._rotate_trackball(QPointF(300+100*np.cos(angle),232+100*np.sin(angle)),
                                  QPointF(300+100*np.cos(angle+.1),232+100*np.sin(angle+.1)))
    basis=preview._view_basis()
    assert np.isfinite(basis).all()
    np.testing.assert_allclose(basis@basis.T,np.eye(3),atol=1e-12)
    assert np.linalg.det(basis)==pytest.approx(1.,abs=1e-12)


@pytest.mark.parametrize('name,direction',[('front',[1,0,0]),('top',[0,0,1]),('side',[0,1,0]),
    ('iso',[1/np.sqrt(3),-1/np.sqrt(3),1/np.sqrt(3)])])
def test_view_buttons_use_expected_axis_and_do_not_modify_geometry(preview,name,direction):
    preview.update_geometry(generate_impeller(BladeParameters()))
    original=deepcopy(preview.base_lines)
    drag(preview,QPoint(300,232),QPoint(350,190))
    QTest.mouseClick(preview.view_buttons[name],Qt.MouseButton.LeftButton)
    np.testing.assert_allclose(preview._view_basis()[2],direction,atol=1e-12)
    for key,value in original.items():np.testing.assert_array_equal(preview.base_lines[key][0],value[0])
    assert preview.view_buttons[name].geometry().bottom()<preview._plot_top-8


def test_fit_keeps_free_orientation_and_contains_all_revolved_surfaces(preview):
    preview.update_geometry(generate_impeller(BladeParameters()))
    drag(preview,QPoint(400,250),QPoint(300,120))
    orientation=preview._view_basis().copy()
    QTest.mouseClick(preview.view_buttons['fit'],Qt.MouseButton.LeftButton)
    np.testing.assert_array_equal(preview._view_basis(),orientation)
    xyz=np.concatenate([f.reshape(-1,3) for f,color in preview.surfaces.values()])
    camera=preview.camera_position;right,up,_=preview._view_basis()
    factor=min(preview.width(),preview.height())/(2*camera['scale'])
    x=((xyz-camera['center'])@right+camera['pan'][0])*factor+preview.width()/2
    y=-((xyz-camera['center'])@up+camera['pan'][1])*factor+(preview.height()+preview._plot_top)/2
    assert x.min()>=0 and x.max()<=preview.width()
    assert y.min()>=preview._plot_top and y.max()<=preview.height()-25
    assert not preview.grab().toImage().isNull()


def test_pan_zoom_and_reset_keep_their_separate_roles(preview):
    preview.update_geometry(generate_impeller(BladeParameters()))
    drag(preview,QPoint(300,232),QPoint(370,270))
    orientation=preview._view_basis().copy()
    drag(preview,QPoint(300,232),QPoint(320,242),Qt.MouseButton.RightButton)
    np.testing.assert_array_equal(preview._view_basis(),orientation)
    assert np.linalg.norm(preview.camera_position['pan'])>0
    position=QPointF(300,232);before=preview.camera_position['scale']
    event=QWheelEvent(position,position,QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,
                      Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(preview,event)
    assert preview.camera_position['scale']<before
    np.testing.assert_array_equal(preview._view_basis(),orientation)
    QTest.mouseClick(preview.view_buttons['reset'],Qt.MouseButton.LeftButton)
    assert preview.camera_position['azimuth']==-45 and preview.camera_position['elevation']==25
    np.testing.assert_array_equal(preview.camera_position['rotation'],np.eye(3))


def test_free_rotation_survives_row_switch_edit_undo_and_annulus():
    app=QApplication.instance() or QApplication([]);w=MainWindow();w.show();app.processEvents()
    try:
        view=w.model_preview_3d
        view._rotate_trackball(QPointF(160,170),QPointF(250,220))
        rotation=view.camera_position['rotation'].copy()
        w.select_blade_row('row-2')
        box=w.angle_editor.table.cellWidget(1,1);box.setValue(box.value()+1);box.editingFinished.emit()
        w.update_geometry();w.undo();w.redo()
        w.annulus_3d.setChecked(True)
        np.testing.assert_array_equal(view.camera_position['rotation'],rotation)
        assert set(view.view_buttons)=={'front','top','side','iso','fit','reset'}
        assert set(w.preview_3d.view_buttons)==set(view.view_buttons)
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()
