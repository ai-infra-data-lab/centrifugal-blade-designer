from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QFormLayout, QSpinBox, QCheckBox
from ..models.parameters import ExportParameters


class ExportSettingsWidget(QGroupBox):
    settingsChanged = Signal()

    def __init__(self) -> None:
        super().__init__("Export")
        form = QFormLayout(self)
        self.digits = QSpinBox()
        self.digits.setRange(1,15)
        self.digits.setValue(6)
        self.repeat = QCheckBox("Repeat first point at end")
        form.addRow("Significant Digits",self.digits)
        form.addRow(self.repeat)
        self.digits.valueChanged.connect(self.settingsChanged)
        self.repeat.toggled.connect(self.settingsChanged)

    def get_settings(self) -> ExportParameters:
        return ExportParameters(self.digits.value(),self.repeat.isChecked())

    def set_settings(self, settings: ExportParameters) -> None:
        self.digits.setValue(settings.significant_digits)
        self.repeat.setChecked(settings.repeat_first_point)
