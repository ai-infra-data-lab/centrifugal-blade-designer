from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QPushButton,QInputDialog,QLabel


class SectionSelector(QWidget):
    selected = Signal(int)
    copyRequested = Signal(bool)
    addRequested = Signal(float)
    deleteRequested = Signal()

    def __init__(self):
        super().__init__();layout=QVBoxLayout(self)
        label = QLabel("Impeller Section • LE/TE shape shared")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.combo=QComboBox();layout.addWidget(self.combo);self.combo.currentIndexChanged.connect(self.selected)
        row=QHBoxLayout();layout.addLayout(row)
        for label,signal in (("Add Span",self._add),("Delete Span",self.deleteRequested.emit)):
            button=QPushButton(label);button.clicked.connect(signal);row.addWidget(button)

    def set_sections(self,sections,index=0):
        self.combo.blockSignals(True);self.combo.clear()
        for s in sections:
            self.combo.addItem("Hub" if s.span==0 else "Tip" if s.span==1 else f"Span {s.span:.6g}")
        self.combo.setCurrentIndex(index);self.combo.blockSignals(False)

    def _add(self):
        value,ok=QInputDialog.getDouble(self,"Add Span Section","Span (0 < span < 1)",.5,.000001,.999999,6)
        if ok:self.addRequested.emit(value)
