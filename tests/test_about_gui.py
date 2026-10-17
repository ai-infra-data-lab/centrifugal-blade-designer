"""Application information is accessible without occupying the editor area."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import pytest
from PySide6.QtWidgets import QApplication,QLabel,QMessageBox
from blade_designer.gui.main_window import MainWindow


@pytest.mark.parametrize('mode',['design','optimization'])
def test_about_action_shows_previous_heading_and_keeps_design_state(mode,monkeypatch):
    app=QApplication.instance() or QApplication([]);w=MainWindow(mode=mode)
    calls=[];monkeypatch.setattr(QMessageBox,'about',lambda *args:calls.append(args))
    try:
        w.show();app.processEvents();before=deepcopy(w.get_parameters());count=w.undo_stack.count()
        assert not any('Centrifugal Compressor Blade Designer' in label.text()
                       or 'Impeller / Vaned Diffuser v0.3' in label.text()
                       for label in w.centralWidget().findChildren(QLabel))
        menu=w.menuBar().actions()[-1].menu();assert menu.title()=='About'
        menu.actions()[0].trigger()
        assert len(calls)==1 and calls[0][0] is w
        assert calls[0][1]=='About Blade Designer'
        for text in ('Centrifugal Compressor Blade Designer','Impeller / Vaned Diffuser v0.3',
                     'βm = 0°: meridional direction','Normalized Meridional',mode.title()):
            assert text in calls[0][2]
        assert w.get_parameters()==before and w.undo_stack.count()==count
    finally:
        w.timer.stop();w.close();w.deleteLater();app.processEvents()
