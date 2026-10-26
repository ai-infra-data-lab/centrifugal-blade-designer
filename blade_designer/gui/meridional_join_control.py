"""Direction at a connected endpoint: inherited tangent or explicit signed turn."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QComboBox
from .control_point_editor import CompactDoubleSpinBox


class MeridionalJoinControl(QWidget):
    changed=Signal()

    def __init__(self,value=None,first=False):
        super().__init__();self._loading=False
        layout=QHBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.mode=QComboBox()
        self.mode.addItems(['開始方向' if first else '正接 G1','開始角から指定' if first else '指定角 G0'])
        self.angle=CompactDoubleSpinBox();self.angle.setDecimals(12)
        self.angle.setRange(-179.999999999,179.999999999);self.angle.setSuffix('°')
        self.angle.setKeyboardTracking(False);self.angle.setMinimumWidth(90)
        self.direction_help='接点位置は共有します。直前の接線（先頭ではStart angle）からの折れ角。正は+Zから+Rへ回転。'
        self.setToolTip(self.direction_help)
        layout.addWidget(self.mode);layout.addWidget(self.angle)
        self.set_value(value)
        self.mode.currentIndexChanged.connect(self._changed)
        self.angle.valueChanged.connect(self._changed)

    def value(self):
        return None if self.mode.currentIndex()==0 else self.angle.value()

    def set_value(self,value):
        self._loading=True
        try:
            self.mode.setCurrentIndex(0 if value is None else 1)
            self.angle.setValue(0. if value is None else value)
            self.angle.setEnabled(value is not None)
        finally:self._loading=False

    def _changed(self,*_):
        self.angle.setEnabled(self.mode.currentIndex()==1)
        if not self._loading:self.changed.emit()
