"""Optional splitter placement and distributions, with main-blade defaults."""
from copy import deepcopy
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox,QFormLayout,QLabel,QCheckBox,QPushButton,QTabWidget
from .control_point_editor import CompactDoubleSpinBox
from .profile_distribution_editor import ProfileDistributionEditor
from ..models.parameters import SplitterParameters


class SplitterEditor(QGroupBox):
    parametersChanged=Signal()
    copyRequested=Signal()
    dragStarted=Signal()
    dragFinished=Signal()
    editFinished=Signal()

    def __init__(self):
        super().__init__("スプリッターを追加 / Enable Splitter")
        self.setCheckable(True);self.setChecked(False)
        form=QFormLayout(self);self.controls={};self._source=None;self._display={};self._profiles=None
        self.angle_editor=None;self.thickness_editor=None
        for name,label,limits in (
            ("hub_start_fraction","Hub開始位置 [%]",(.001,99.999)),
            ("tip_start_fraction","Tip開始位置 [%]",(.001,99.999)),
            ("pitch_fraction","主翼間の位置 [%]",(.001,99.999)),
            ("thickness_scale","厚さ倍率",(.001,100.))):
            box=CompactDoubleSpinBox();box.setDecimals(6);box.setRange(*limits);box.setKeyboardTracking(False)
            form.addRow(label,box);self.controls[name]=box
            box.valueChanged.connect(lambda *_:self.parametersChanged.emit())
        note=QLabel("各主翼間に1枚（主翼と同数）。開始位置は主翼のLE=0%、TE=100%。周方向は回転方向へ1ピッチの割合。端部形状・TE位置・TE Rakeは主翼を継承します。")
        note.setWordWrap(True);form.addRow(note)
        self.independent=QCheckBox("主翼からコピーして角度・厚さを独立編集")
        form.addRow(self.independent)
        axis_note=QLabel("専用分布の横軸も主翼LE=0、TE=1です。開始位置以降を使用します。独立編集後は主翼β・厚さの変更に追従しません。厚さグラフは倍率適用前の値です。")
        axis_note.setWordWrap(True);form.addRow(axis_note)
        self.copy_button=QPushButton("現在の主翼から再コピー")
        self.copy_button.clicked.connect(lambda *_:self.copyRequested.emit());form.addRow(self.copy_button)
        self.distributions=QTabWidget();form.addRow(self.distributions)
        self.summary=QLabel();self.summary.setWordWrap(True);form.addRow(self.summary)
        self.set_parameters(None)
        self.independent.toggled.connect(self._independent_changed)
        self.toggled.connect(lambda *_:self.parametersChanged.emit())

    def _independent_changed(self,checked):
        if checked:self.copyRequested.emit()
        else:
            self._profiles=None;self._show_mode();self.parametersChanged.emit()

    def _show_mode(self):
        self.copy_button.setEnabled(self.independent.isChecked())
        self.distributions.setVisible(self.independent.isChecked())

    def set_profiles(self,profiles):
        self._profiles=deepcopy(profiles)
        if self.angle_editor is None:
            for attr,kind,label in (("angle_editor","blade_angle","Blade Angle"),("thickness_editor","thickness","Thickness")):
                editor=ProfileDistributionEditor(kind);setattr(self,attr,editor);self.distributions.addTab(editor,label)
                editor.plot.setLabel("bottom","Main blade normalized meridional (0=LE, 1=TE)")
                editor.pointsChanged.connect(self.parametersChanged.emit)
                for signal in ("dragStarted","dragFinished","editFinished"):
                    getattr(editor,signal).connect(getattr(self,signal).emit)
        for editor,name in ((self.angle_editor,"blade_angle"),(self.thickness_editor,"thickness")):
            editor.set_profiles([(p.span,"Hub" if p.span==0 else "Tip" if p.span==1 else f"Span {p.span:.6g}",getattr(p,name).points) for p in profiles])
        self._show_mode()

    def set_parameters(self,settings):
        self._source=deepcopy(settings);defaults=SplitterParameters() if settings is None else settings
        self.blockSignals(True);self.setChecked(settings is not None)
        for name,box in self.controls.items():
            box.blockSignals(True);factor=1 if name=="thickness_scale" else 100
            box.setValue(getattr(defaults,name)*factor);self._display[name]=box.value();box.blockSignals(False)
        self.independent.blockSignals(True);self.independent.setChecked(defaults.sections is not None);self.independent.blockSignals(False)
        if defaults.sections is not None:self.set_profiles(defaults.sections)
        else:self._profiles=None
        self._show_mode();self.blockSignals(False)

    def get_parameters(self):
        if not self.isChecked():return None
        result=deepcopy(self._source) if self._source is not None else SplitterParameters()
        for name,box in self.controls.items():
            if self._source is None or box.value()!=self._display[name]:
                setattr(result,name,box.value()/(1 if name=="thickness_scale" else 100))
        result.sections=deepcopy(self._profiles) if self.independent.isChecked() else None
        for profile in result.sections or []:
            profile.blade_angle.points=self.angle_editor.series[profile.span].get_points()
            profile.thickness.points=self.thickness_editor.series[profile.span].get_points()
        return result

    def show_geometry(self,geometry,main_count):
        if not geometry.splitter_sections:
            self.summary.clear();return
        h,t=(geometry.splitter_sections[i].camber for i in (0,-1))
        self.summary.setText(f"表示中: 主翼 {main_count}枚 + スプリッター {main_count}枚\n"
            f"LE Hub R/Z: {h.r[0]:.6g} / {h.z[0]:.6g} mm\n"
            f"LE Tip R/Z: {t.r[0]:.6g} / {t.z[0]:.6g} mm")
        if self.independent.isChecked() and self._profiles:
            settings=self.get_parameters()
            for section in geometry.splitter_sections:
                if section.span not in self.angle_editor.series:continue
                f=(1-section.span)*settings.hub_start_fraction+section.span*settings.tip_start_fraction
                x=f+(1-f)*section.camber.m_blade_norm
                self.angle_editor.update_profile_distribution(section.span,x,section.beta_m_deg)
                self.thickness_editor.update_profile_distribution(section.span,x,section.thickness/settings.thickness_scale)
