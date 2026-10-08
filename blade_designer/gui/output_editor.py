from copy import deepcopy
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QFormLayout,QComboBox,QLineEdit,QLabel
from .control_point_editor import CompactDoubleSpinBox


class ImpellerOutputEditor(QWidget):
    parametersChanged=Signal()

    def __init__(self,params):
        super().__init__();form=QFormLayout(self);self.controls={};self._loading=False
        for key,label in (("blade_le_fraction","Component IMP_LE / m_flow_norm"),("blade_te_fraction","Component IMP_TE / m_flow_norm")):
            box=CompactDoubleSpinBox();box.setDecimals(12);box.setRange(0,1);box.setSingleStep(.01)
            box.valueChanged.connect(self._changed);self.controls[key]=box;form.addRow(label,box)
        for key,label,items in (("geometry_unit","TurboGrid length unit",["MM","CM","M"]),("rotation_axis","TurboGrid rotation axis",["Z","X","Y"])):
            box=QComboBox();box.addItems(items);box.currentIndexChanged.connect(self._changed)
            self.controls[key]=box;form.addRow(label,box)
        for key,label in (("leading_edge_type","TurboGrid LE setting"),("trailing_edge_type","TurboGrid TE setting")):
            box=QComboBox();box.addItems(["auto","EllipseEnd","CutOffEnd","SquareEnd"])
            box.currentIndexChanged.connect(self._changed);self.controls[key]=box;form.addRow(label,box)
        for key,label in (("hub_curve_filename","Hub filename"),("shroud_curve_filename","Shroud filename"),("profile_curve_filename","Profile filename")):
            box=QLineEdit();box.textChanged.connect(self._changed);self.controls[key]=box;form.addRow(label,box)
        note=QLabel("Internal length: mm. Export converts units/axis automatically. Blade count is shared with Diffuser Geometry. LE/TE shape is defined independently per section. Edit blade endpoint positions in Meridional → Blade Edges.")
        note.setWordWrap(True);form.addRow(note);self.set_parameters(params)

    def _changed(self,*args):
        if not self._loading:self.parametersChanged.emit()

    def set_parameters(self,params):
        self._loading=True;self._source=deepcopy(params);self._display={}
        for key,box in self.controls.items():
            group=params if hasattr(params,key) else params.turbogrid;value=getattr(group,key)
            if isinstance(box,QComboBox):box.setCurrentText(value);shown=box.currentText()
            elif isinstance(box,QLineEdit):box.setText(value);shown=box.text()
            else:box.setValue(value);shown=box.value()
            self._display[key]=shown
        self._loading=False

    def apply_to(self,params):
        for key,box in self.controls.items():
            group=params if hasattr(params,key) else params.turbogrid
            value=box.currentText() if isinstance(box,QComboBox) else box.text() if isinstance(box,QLineEdit) else box.value()
            original=self._source if hasattr(self._source,key) else self._source.turbogrid
            setattr(group,key,getattr(original,key) if value==self._display[key] else value)
