"""Independent derivative settings, committed on focus loss/Enter."""
from copy import deepcopy
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox,QFormLayout,QLabel,QComboBox
from .control_point_editor import CompactDoubleSpinBox
from ..models.parameters import ImpellerTrimParameters


class ImpellerTrimEditor(QGroupBox):
    parametersChanged=Signal()

    def __init__(self):
        super().__init__('派生設計 / Shroud・外径カット')
        self.setCheckable(True);self.setChecked(False)
        self._source=None;self._shown={};self.controls={}
        form=QFormLayout(self)
        self.mode=QComboBox()
        for text,value in (('外径カットなし','off'),('指定外径 [mm]','diameter'),('元外径からの切削率 [%]','percent')):
            self.mode.addItem(text,value)
        for key,label,maximum in (('shroud_area_cut_percent','基準Gross面積の削減率 [%]',99.9),
                                  ('diameter_mm','切削後の外径 [mm]',100000.),
                                  ('diameter_cut_percent','外径の切削率 [%]',99.9)):
            box=CompactDoubleSpinBox();box.setRange(0,maximum);box.setDecimals(6)
            box.setKeyboardTracking(False);self.controls[key]=box;form.addRow(label,box)
            box.valueChanged.connect(self.parametersChanged)
        form.insertRow(1,'外径の指定方法',self.mode)
        self.downstream=QComboBox()
        self.downstream.addItem('後流も同じ率でカット','cut')
        self.downstream.addItem('TEから後流端まで滑らかに元へ戻す','restore')
        self.downstream.setToolTip('選択Impellerの派生Shroudだけに適用します。共有子午面・他翼列は変更しません。')
        form.insertRow(1,'Shroudカットの後流側',self.downstream)
        self.downstream.currentIndexChanged.connect(self.parametersChanged)
        self.status=QLabel();self.status.setWordWrap(True);form.addRow(self.status)
        note=QLabel('元の角度・厚さ・子午面を保持し、生成済みの翼面を切り出します。'
                    '面積比は元の子午面の基準断面で比較します。\n'
                    '翼Tipとケーシングを変更し、既存のLE/TEクリアランス [mm]を維持します。'
                    '流量・圧力比の予測値ではありません。派生形状のTurboGrid/CAD出力は未対応です。')
        note.setWordWrap(True);form.addRow(note)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.toggled.connect(self.parametersChanged);self._mode_changed()

    def _mode_changed(self,*_):
        mode=self.mode.currentData()
        self.controls['diameter_mm'].setEnabled(mode=='diameter')
        self.controls['diameter_cut_percent'].setEnabled(mode=='percent')
        self.parametersChanged.emit()

    def set_parameters(self,settings):
        self.blockSignals(True);self._source=deepcopy(settings)
        self.setChecked(settings is not None)
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(self.mode.findData(settings.diameter_mode if settings else 'off'))
        self.mode.blockSignals(False)
        self.downstream.blockSignals(True)
        self.downstream.setCurrentIndex(self.downstream.findData(settings.shroud_downstream_mode if settings else 'cut'))
        self.downstream.blockSignals(False)
        for key,box in self.controls.items():
            box.blockSignals(True);box.setValue(getattr(settings,key) if settings else 0.)
            self._shown[key]=box.value();box.blockSignals(False)
        self._mode_changed();self.status.clear();self.blockSignals(False)

    def get_parameters(self):
        if not self.isChecked():return None
        result=deepcopy(self._source) if self._source is not None else ImpellerTrimParameters()
        result.diameter_mode=self.mode.currentData()
        result.shroud_downstream_mode=self.downstream.currentData()
        for key,box in self.controls.items():
            if box.value()!=self._shown.get(key):setattr(result,key,box.value())
        return result

    def show_geometry(self,geometry):
        report=geometry.trim_report
        base=geometry.source_geometry or geometry
        text=f'元のHub TE径: {2*base.sections[0].camber.r[-1]:.6g} mm'
        if report:
            text+=f" → {report['diameter_mm']:.6g} mm\n元の基準断面の面積比: {report['reference_area_ratio']:.6g}"
            if self.downstream.currentData()=='restore' and report['reference_area_ratio']<1:
                text+='（翼部。後流は元のShroudへ復元）'
        self.status.setText(text)
