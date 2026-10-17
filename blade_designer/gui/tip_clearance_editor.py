"""Per-impeller clearance controls; edits commit on Enter/focus loss."""
from copy import deepcopy
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox,QFormLayout,QLabel
from .control_point_editor import CompactDoubleSpinBox
from ..models.parameters import TipClearanceParameters


class TipClearanceEditor(QGroupBox):
    parametersChanged=Signal()

    def __init__(self):
        super().__init__('オープンインペラ / Tip Clearance')
        self.setCheckable(True);self.setChecked(False)
        self._source=None;self._shown={};self.controls={}
        form=QFormLayout(self)
        for key,label in (('le_mm','LE clearance [mm]'),('te_mm','TE clearance [mm]')):
            box=CompactDoubleSpinBox();box.setDecimals(6);box.setRange(0.,10000.)
            box.setKeyboardTracking(False);self.controls[key]=box;form.addRow(label,box)
            box.valueChanged.connect(lambda *_:self.parametersChanged.emit())
        note=QLabel('Shroudはケーシングとして固定。Hub側への法線距離をmmで指定し、'
                    'LE–TE間はケーシング沿いの距離で線形補間します。\n'
                    '子午面のShroud LE/TE欄はケーシング上の基準です。実際の翼Tipは内側に生成します。'
                    '未指定・0 mmは従来形状です。')
        note.setWordWrap(True);form.addRow(note)
        self.toggled.connect(lambda *_:self.parametersChanged.emit())

    def set_parameters(self,settings):
        self.blockSignals(True)
        self._source=deepcopy(settings)
        self.setChecked(settings is not None)
        for name,box in self.controls.items():
            box.blockSignals(True);box.setValue(getattr(settings,name) if settings is not None else 0.)
            self._shown[name]=box.value();box.blockSignals(False)
        self.blockSignals(False)

    def get_parameters(self):
        if not self.isChecked():return None
        result=deepcopy(self._source) if self._source is not None else TipClearanceParameters()
        for name,box in self.controls.items():
            if box.value()!=self._shown.get(name):setattr(result,name,box.value())
        return result
