import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import numpy as np
from PySide6.QtWidgets import QApplication
from blade_designer.gui.meridional_editor import MeridionalEditor


def test_segment_operations_and_preserved_view():
 app=QApplication.instance() or QApplication([])
 e=MeridionalEditor();e.show();app.processEvents()
 e.plot.setRange(xRange=(0,10),yRange=(40,50),padding=0)
 before=np.array(e.plot.viewRange())
 e.add_segment(True);assert len(e.get_curves()[0].segments)==4
 e.move_segment(-1);assert e.table.currentRow()==2
 e.delete_segment();assert len(e.get_curves()[0].segments)==3
 e.table.cellWidget(1,2).setValue(-1)
 assert "ERROR" in e.message.text()
 np.testing.assert_allclose(e.plot.viewRange(),before)
 e.selector.setCurrentIndex(1);assert e.start_controls['start_r'].value()==65
 e.close()
