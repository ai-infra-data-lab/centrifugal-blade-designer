import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import pytest
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
from blade_designer.gui.main_window import MainWindow
from blade_designer.models.parameters import SplitterParameters,TipClearanceParameters
from blade_designer.fileio.export_readiness import assess_exports
from test_impeller_te_rake import radial_parameters
from test_splitter_turbogrid import blade_sets


@pytest.mark.parametrize('clearance',[False,True])
def test_menu_exports_current_splitter_and_reports_correct_tip_number(tmp_path,monkeypatch,clearance):
    app=QApplication.instance() or QApplication([])
    p=radial_parameters();p.splitter=SplitterParameters()
    if clearance:p.tip_clearance=TipClearanceParameters(.5,1.)
    w=MainWindow(default_parameters=p);w.show();app.processEvents()
    try:
        before=deepcopy(w.get_parameters());case=tmp_path/'case';warnings=[]
        monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(case))
        monkeypatch.setattr(QMessageBox,'warning',lambda *a:warnings.append(a[-1]))
        w.export_turbogrid_dialog()
        assert not warnings
        assert [name for name,_ in blade_sets(case/'profile.curve')]==['Main','Splitter']
        assert 'Main + Splitter' in w.statusBar().currentMessage()
        if clearance:assert 'Profile Number 3' in w.statusBar().currentMessage()
        assert w.get_parameters()==before
        readiness=assess_exports(before)
        profile=next(route for route in readiness.routes if route.name=='Profile Points')
        assert profile.status=='INPUTS_READY'
        assert any(c.code=='serialized' and c.state=='PASS' for c in profile.checks)
        assert 'ANSYS Import/Mesh were not run' in readiness.note
    finally:w.timer.stop();w.close();w.deleteLater();app.processEvents()
