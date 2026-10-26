"""Independent meridional definitions and upstream G1 selection."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QFormLayout,QCheckBox,QComboBox,QLabel
from .meridional_join_control import MeridionalJoinControl


class ElementWallsEditor(QWidget):
    settingsChanged=Signal()

    def __init__(self):
        super().__init__();layout=QFormLayout(self)
        self.independent=QCheckBox('独立したHub/Shroud / Independent walls')
        self.upstream=QComboBox()
        self.note=QLabel('接点のR/Zを引き継ぎ、正接または指定した折れ角で接続します。線/円弧の寸法はこの要素が保持します。')
        self.note.setWordWrap(True)
        layout.addRow(self.independent);layout.addRow('上流要素 / Upstream',self.upstream)
        self.joins={side:MeridionalJoinControl() for side in ('hub','shroud')}
        for side,control in self.joins.items():
            layout.addRow(side.title()+' 接続',control);control.changed.connect(self.settingsChanged.emit)
        layout.addRow(self.note)
        self.independent.toggled.connect(self.settingsChanged.emit)
        self.upstream.currentIndexChanged.connect(lambda *_:self.settingsChanged.emit())

    def set_rows(self,rows,active):
        self.independent.blockSignals(True);self.upstream.blockSignals(True)
        try:
            self.independent.setChecked(active.independent_meridional)
            self.independent.setEnabled(active.kind!='meridional')
            links={row.identifier:row.upstream_row for row in rows}
            self.upstream.clear();self.upstream.addItem('未接続 / None',None)
            for row in rows:
                current=row.identifier;visited=set()
                while current is not None and current not in visited and current!=active.identifier:
                    visited.add(current);current=links.get(current)
                if current==active.identifier:continue
                self.upstream.addItem(row.name,row.identifier)
            self.upstream.setCurrentIndex(max(0,self.upstream.findData(active.upstream_row)))
            self.upstream.setEnabled(active.independent_meridional)
            for side,control in self.joins.items():
                control.set_value(getattr(active,side+'_inlet_turn_deg'))
                control.setEnabled(active.independent_meridional and active.upstream_row is not None)
        finally:
            self.independent.blockSignals(False);self.upstream.blockSignals(False)
