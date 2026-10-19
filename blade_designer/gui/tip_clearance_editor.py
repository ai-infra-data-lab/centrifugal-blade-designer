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
        self.analysis_group=QGroupBox('解析用Shroudを別作成（翼Tip固定）')
        self.analysis_group.setCheckable(True);self.analysis_group.setChecked(False)
        analysis_form=QFormLayout(self.analysis_group);self.analysis_controls={}
        for key,label in (('analysis_le_mm','解析 LE clearance [mm]'),('analysis_te_mm','解析 TE clearance [mm]')):
            box=CompactDoubleSpinBox();box.setDecimals(6);box.setRange(0.,10000.);box.setKeyboardTracking(False)
            self.analysis_controls[key]=box;analysis_form.addRow(label,box)
            box.valueChanged.connect(lambda *_:self.parametersChanged.emit())
        form.addRow(self.analysis_group)
        self.analysis_group.toggled.connect(self._analysis_toggled)
        note=QLabel('Shroudはケーシングとして固定。Hub側への法線距離をmmで指定し、'
                    'LE–TE間はケーシング沿いの距離で線形補間します。\n'
                    '子午面のShroud LE/TE欄はケーシング上の基準です。実際の翼Tipは内側に生成します。'
                    '上段は図面用の隙間です。解析用は同じ図面ケーシング法線を基準に、'
                    '固定したTipからShroudだけを動かします。TurboGridは解析用、Mechanical CADは図面用です。')
        note.setWordWrap(True);form.addRow(note)
        self.toggled.connect(lambda *_:self.parametersChanged.emit())

    def _analysis_toggled(self,checked):
        if checked and (self._source is None or self._source.analysis_le_mm is None):
            for name,box in self.analysis_controls.items():
                box.blockSignals(True);box.setValue(self.controls[name.removeprefix('analysis_')].value());box.blockSignals(False)
        self.parametersChanged.emit()

    def set_parameters(self,settings):
        self.blockSignals(True)
        self._source=deepcopy(settings)
        self.setChecked(settings is not None)
        for name,box in self.controls.items():
            box.blockSignals(True);box.setValue(getattr(settings,name) if settings is not None else 0.)
            self._shown[name]=box.value();box.blockSignals(False)
        self.analysis_group.blockSignals(True)
        self.analysis_group.setChecked(settings is not None and settings.analysis_le_mm is not None)
        self.analysis_group.blockSignals(False)
        for name,box in self.analysis_controls.items():
            value=getattr(settings,name) if settings is not None else None
            box.blockSignals(True);box.setValue(value if value is not None else 0.)
            self._shown[name]=box.value();box.blockSignals(False)
        self.blockSignals(False)

    def get_parameters(self):
        if not self.isChecked():return None
        result=deepcopy(self._source) if self._source is not None else TipClearanceParameters()
        for name,box in self.controls.items():
            if box.value()!=self._shown.get(name):setattr(result,name,box.value())
        for name,box in self.analysis_controls.items():
            if not self.analysis_group.isChecked():setattr(result,name,None)
            elif getattr(result,name) is None or box.value()!=self._shown.get(name):setattr(result,name,box.value())
        return result
