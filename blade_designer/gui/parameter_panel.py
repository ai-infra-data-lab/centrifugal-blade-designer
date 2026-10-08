from copy import deepcopy
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QSpinBox, QGroupBox, QFormLayout, QVBoxLayout, QPushButton, QComboBox
from ..models.parameters import BladeParameters, EdgeType, SurfaceMapping
from .control_point_editor import CompactDoubleSpinBox
from .export_settings_widget import ExportSettingsWidget


class ParameterPanel(QWidget):
    parametersChanged = Signal()
    editAngleRequested = Signal()
    editThicknessRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False
        self._source = BladeParameters()
        self.controls: dict = {}
        self.groups = {}
        layout = QVBoxLayout(self)
        for title, definitions in (
            ("Geometry", [("r_le","R LE [mm]"),("r_te","R TE [mm]"),("theta_le_deg","Theta LE [deg]"),("vane_count","Vane Count")]),
            ("Output Points",[("le_points","LE"),("ps_points","PS"),("te_points","TE"),("ss_points","SS")])):
            group = QGroupBox(title)
            self.groups[title] = group
            form = QFormLayout(group)
            for name,label in definitions:
                if name == "vane_count" or name.endswith("_points"):
                    box = QSpinBox()
                    box.setRange(1 if name == "vane_count" else 2,10000)
                else:
                    box = CompactDoubleSpinBox()
                    box.setDecimals(12)
                    box.setRange(-1e12,1e12)
                box.valueChanged.connect(self._changed)
                self.controls[name] = box
                form.addRow(label,box)
            layout.addWidget(group)
        for label,signal in (("Diffuser Blade Angle — Edit Control Points",self.editAngleRequested),
                             ("Diffuser Thickness — Edit Control Points",self.editThicknessRequested)):
            button = QPushButton(label)
            button.clicked.connect(signal)
            layout.insertWidget(1 if "Angle" in label else 2,button)
        for side,title in (("le","Leading Edge"),("te","Trailing Edge")):
            group = QGroupBox(title)
            self.groups[title] = group
            form = QFormLayout(group)
            combo = QComboBox()
            for kind in EdgeType:
                combo.addItem(kind.value.title(),kind)
            ratio = CompactDoubleSpinBox()
            ratio.setDecimals(12)
            ratio.setRange(.000001,1e6)
            ratio.setValue(1.)
            ratio.setSingleStep(.1)
            self.controls[side+"_type"] = combo
            self.controls[side+"_ellipse_ratio"] = ratio
            combo.currentIndexChanged.connect(self._changed)
            ratio.valueChanged.connect(self._changed)
            form.addRow("Type",combo)
            form.addRow("Ellipse Ratio",ratio)
            layout.insertWidget(3 if side == "le" else 4,group)
        group = QGroupBox("Pressure Side Mapping")
        form = QFormLayout(group)
        self.mapping = QComboBox()
        for label,mapping in (("Auto (net turning estimate)",SurfaceMapping.AUTO),
                              ("+Normal = PS",SurfaceMapping.POSITIVE_IS_PS),
                              ("-Normal = PS",SurfaceMapping.NEGATIVE_IS_PS)):
            self.mapping.addItem(label,mapping)
        self.mapping.currentIndexChanged.connect(self._changed)
        form.addRow(self.mapping)
        layout.insertWidget(5,group)
        self.export_settings = ExportSettingsWidget()
        self.export_settings.settingsChanged.connect(self._changed)
        layout.addWidget(self.export_settings)
        layout.addStretch()
        self.set_parameters(BladeParameters())

    def _changed(self) -> None:
        for side in ("le","te"):
            if side+"_type" in self.controls:
                self.controls[side+"_ellipse_ratio"].setEnabled(self.controls[side+"_type"].currentData() == EdgeType.ELLIPTICAL)
        if not self._loading:
            self.parametersChanged.emit()

    def get_parameters(self) -> BladeParameters:
        p = deepcopy(self._source)
        for name,box in self.controls.items():
            group = p.geometry if hasattr(p.geometry,name) else p.output_points if hasattr(p.output_points,name) else p.edges
            value = EdgeType(box.currentData()) if isinstance(box,QComboBox) else box.value()
            if value != self._display_values[name]:
                setattr(group,name,value)
        p.surface_mapping = SurfaceMapping(self.mapping.currentData())
        p.export = self.export_settings.get_settings()
        return p

    def set_parameters(self, p: BladeParameters) -> None:
        for name,box in self.controls.items():
            group = p.geometry if hasattr(p.geometry,name) else p.output_points if hasattr(p.output_points,name) else p.edges
            if not isinstance(box,QComboBox) and not box.minimum() <= getattr(group,name) <= box.maximum():
                raise ValueError(f"{name} is outside the GUI range.")
        self._loading = True
        try:
            self._source = deepcopy(p)
            for name,box in self.controls.items():
                group = p.geometry if hasattr(p.geometry,name) else p.output_points if hasattr(p.output_points,name) else p.edges
                value = getattr(group,name)
                if isinstance(box,QComboBox):
                    box.setCurrentIndex(box.findData(value))
                else:
                    box.setValue(value)
            self.mapping.setCurrentIndex(self.mapping.findData(p.surface_mapping))
            self.export_settings.set_settings(p.export)
            self._display_values = {name: box.currentData() if isinstance(box,QComboBox) else box.value() for name,box in self.controls.items()}
            self._changed()
        finally:
            self._loading = False
        self.parametersChanged.emit()
