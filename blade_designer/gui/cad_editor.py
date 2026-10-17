"""Optional CAD settings, with an explicitly labelled provisional disk action."""
from copy import deepcopy
from dataclasses import asdict
import json
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QLabel,QComboBox,QCheckBox,QPushButton,QPlainTextEdit,QHBoxLayout
from .control_point_editor import CompactDoubleSpinBox
from ..models.cad import CadExportParameters,MechanicalExportScope,FilletMode,validate_cad_parameters
from ..fileio.project_io import _curve
from ..cad.client import backend_python


class CadEditor(QWidget):
    parametersChanged=Signal()
    actionRequested=Signal(str)
    cancelRequested=Signal()
    provisionalDiskRequested=Signal()

    def __init__(self):
        super().__init__();self._source=CadExportParameters();self._display={};self._backside=None
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.backend=QLabel()
        try:self.backend.setText("Open CASCADE (OCP), separate process: "+str(backend_python()))
        except Exception:self.backend.setText("CAD backend UNAVAILABLE — coordinate editing remains available")
        self.backend.setWordWrap(True);form.addRow("CAD Backend",self.backend)
        self.hub_enabled=QCheckBox("Enabled");self.shroud_enabled=QCheckBox("Disabled (open impeller)");self.shroud_enabled.setEnabled(False)
        self.radius=self.spin(.000001,10000,6);self.tolerance=self.spin(.000001,1.,6)
        self.radius.setToolTip("根元フィレットの半径をmmで入力。Enterまたはフォーカス移動で確定し、Generate CADで再生成します。")
        form.addRow("Hub Fillet",self.hub_enabled);form.addRow("根元フィレットR / Root R [mm]",self.radius);form.addRow("Shroud Fillet",self.shroud_enabled)
        self.mode=QComboBox()
        for v in FilletMode:self.mode.addItem(v.value,v.value)
        form.addRow("Fillet Mode",self.mode)
        self.scope=QComboBox()
        for v in MechanicalExportScope:self.scope.addItem(v.value,v.value)
        form.addRow("Mechanical Model Scope",self.scope)
        self.mechanical=QCheckBox("Enabled");self.turbogrid=QCheckBox("Enabled");self.step=QCheckBox("STEP (mm / Z)")
        form.addRow("Mechanical Export",self.mechanical);form.addRow("TurboGrid Export",self.turbogrid);form.addRow("Export Format",self.step);form.addRow("Surface tolerance [mm]",self.tolerance)
        self.bore_known=QCheckBox("Bore radius is specified");self.bore=self.spin(0,100000,6)
        form.addRow(self.bore_known);form.addRow("Bore radius [mm]",self.bore)
        self.disk_kind=QLabel();self.disk_kind.setWordWrap(True);layout.addWidget(self.disk_kind)
        self.provisional_disk=QPushButton("仮ディスクを作成・表示 / Create Provisional Disk")
        self.provisional_disk.clicked.connect(self.provisionalDiskRequested.emit);layout.addWidget(self.provisional_disk)
        hint=QLabel("ディスク裏面は外周側から内径側へ定義し、末端RをBore radiusへ一致させます。Hub出口→裏面開始、裏面末端→Hub入口Zの内径点→Hub入口を直線端面で閉じます。仮寸法は構造CAD用で、TurboGridの所属範囲を変更しません。")
        hint.setWordWrap(True);layout.addWidget(hint)
        self.backside=QPlainTextEdit();self.backside.setPlaceholderText('Disk backside JSON: start_z, start_r, start_angle_deg, segments (length / radius,sweep_deg,clockwise), export_points')
        self.backside.setMinimumHeight(110);layout.addWidget(self.backside)
        self.apply_disk=QPushButton("裏面を適用 / Apply Backside");layout.addWidget(self.apply_disk);self.apply_disk.clicked.connect(self.apply_pending_disk)
        self.status=QLabel("寸法未入力なら仮ディスク作成ボタン、またはCAD生成時の自動仮設定を使用できます。");self.status.setWordWrap(True);layout.addWidget(self.status)
        self.buttons={};row=QHBoxLayout();layout.addLayout(row)
        for action,label in (("validate","Validate CAD"),("generate","Generate CAD"),("mechanical","Export Mechanical"),("turbogrid","Export TurboGrid"),("both","Export Both")):
            button=QPushButton(label);button.clicked.connect(lambda checked=False,action=action:self.actionRequested.emit(action));self.buttons[action]=button
            if action=="mechanical":row=QHBoxLayout();layout.addLayout(row)
            row.addWidget(button)
        self.cancel=QPushButton("Cancel CAD");self.cancel.setEnabled(False);self.cancel.clicked.connect(self.cancelRequested.emit);layout.addWidget(self.cancel)
        note=QLabel("Profile Pointsにはフィレットを含みません。TurboGrid CAD STEPは中間形式です。対応形式への変換とANSYS実機Import/Meshは別途確認が必要です。")
        note.setWordWrap(True);layout.addWidget(note);layout.addStretch()
        self.set_parameters(CadExportParameters())
        for box in (self.hub_enabled,self.mechanical,self.turbogrid,self.step,self.bore_known):box.toggled.connect(self._changed)
        for box in (self.radius,self.tolerance,self.bore):box.valueChanged.connect(self._changed)
        for box in (self.mode,self.scope):box.currentIndexChanged.connect(self._changed)

    @staticmethod
    def spin(lo,hi,digits):
        box=CompactDoubleSpinBox();box.setDecimals(digits);box.setRange(lo,hi);box.setKeyboardTracking(False);return box

    def _changed(self,*args):
        self.bore.setEnabled(self.bore_known.isChecked());self._update_disk_kind(self.get_parameters().disk);self.parametersChanged.emit()

    def set_parameters(self,settings):
        self._source=deepcopy(settings);self._backside=deepcopy(settings.disk.backside)
        self.blockSignals(True)
        for box,value in ((self.hub_enabled,settings.fillet.hub_enabled),(self.mechanical,settings.mechanical_enabled),(self.turbogrid,settings.turbogrid_enabled),(self.step,settings.step_enabled),(self.bore_known,settings.disk.bore_radius_mm is not None)):
            box.blockSignals(True);box.setChecked(value);box.blockSignals(False)
        for name,box,value in (("radius",self.radius,settings.fillet.hub_radius_mm),("tolerance",self.tolerance,settings.surface_tolerance_mm),("bore",self.bore,settings.disk.bore_radius_mm or 0.)):
            box.blockSignals(True);box.setValue(value);self._display[name]=box.value();box.blockSignals(False)
        self.bore.setEnabled(self.bore_known.isChecked())
        for box,value in ((self.mode,settings.fillet.mode.value),(self.scope,settings.mechanical_scope.value)):
            box.blockSignals(True);box.setCurrentIndex(box.findData(value));box.blockSignals(False)
        self._backside_text="" if self._backside is None else json.dumps(asdict(self._backside),ensure_ascii=False,indent=2)
        self.backside.setPlainText(self._backside_text);self.blockSignals(False)
        self._update_disk_kind(settings.disk)

    def _update_disk_kind(self,disk):
        if disk.provisional and (disk.backside is None or disk.bore_radius_mm is None):
            self.disk_kind.setText("仮ディスク / PROVISIONAL: 寸法未入力。仮寸法を再作成するか入力を補ってください。")
            return
        self.disk_kind.setText((f"仮ディスク / PROVISIONAL: 内径D={2*disk.bore_radius_mm:g} mm、裏面Z={disk.backside.start_z:g} mm、外径D={2*disk.backside.start_r:g} mm。構造CAD専用。" if disk.provisional else
            "Disk dimensions: unset (CAD生成時に仮寸法を作成)" if disk.backside is None and disk.bore_radius_mm is None else "Disk dimensions: manually specified"))

    def get_parameters(self):
        p=deepcopy(self._source);p.fillet.hub_enabled=self.hub_enabled.isChecked();p.fillet.shroud_enabled=False
        p.mechanical_enabled=self.mechanical.isChecked();p.turbogrid_enabled=self.turbogrid.isChecked();p.step_enabled=self.step.isChecked()
        p.fillet.mode=FilletMode(self.mode.currentData());p.mechanical_scope=MechanicalExportScope(self.scope.currentData())
        if self.radius.value()!=self._display["radius"]:p.fillet.hub_radius_mm=self.radius.value()
        if self.tolerance.value()!=self._display["tolerance"]:p.surface_tolerance_mm=self.tolerance.value()
        if not self.bore_known.isChecked():p.disk.bore_radius_mm=None
        elif p.disk.bore_radius_mm is None or self.bore.value()!=self._display["bore"]:p.disk.bore_radius_mm=self.bore.value()
        p.disk.backside=deepcopy(self._backside);return p

    def apply_pending_disk(self):
        for box in (self.radius,self.tolerance,self.bore):box.interpretText()
        text=self.backside.toPlainText().strip()
        if text==self._backside_text.strip():return True
        try:
            value=None if not text else _curve(json.loads(text))
            if value is not None:
                from ..geometry.meridional_segments import generate_meridional
                generate_meridional(value)
            self._backside=value;self._backside_text=text;self._update_disk_kind(self.get_parameters().disk);self.parametersChanged.emit();self.status.setText("Disk backside applied; structural model still requires CAD validation.");return True
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            self.status.setText("Disk input error: "+str(exc));return False

    def set_busy(self,busy):
        for button in self.buttons.values():button.setEnabled(not busy)
        self.provisional_disk.setEnabled(not busy)
        self.cancel.setEnabled(busy)
