"""Independent meridional definitions and upstream G1 selection."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QFormLayout,QCheckBox,QComboBox,QLabel


class ElementWallsEditor(QWidget):
    settingsChanged=Signal()

    def __init__(self):
        super().__init__();layout=QFormLayout(self)
        self.independent=QCheckBox('独立したHub/Shroud / Independent walls')
        self.upstream=QComboBox()
        self.note=QLabel('接続すると、上流出口のR/Zと接線を引き継ぎます。線/円弧の寸法はこの要素の定義を保持します。')
        self.note.setWordWrap(True)
        layout.addRow(self.independent);layout.addRow('上流要素 / Upstream G1',self.upstream);layout.addRow(self.note)
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
        finally:
            self.independent.blockSignals(False);self.upstream.blockSignals(False)
