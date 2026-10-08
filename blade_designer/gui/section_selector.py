from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QPushButton,QInputDialog,QLabel


class SectionSelector(QWidget):
    selected = Signal(int)
    copyRequested = Signal(bool)
    addRequested = Signal(float)
    deleteRequested = Signal()

    def __init__(self):
        super().__init__();layout=QVBoxLayout(self)
        layout.addWidget(QLabel("Blade View / Full Annulus Section • LE/TE shape shared"))
        self.combo=QComboBox();layout.addWidget(self.combo);self.combo.currentIndexChanged.connect(self.selected)
        row=QHBoxLayout();layout.addLayout(row)
        for label,signal in (("Copy Hub → Tip",lambda:self.copyRequested.emit(True)),("Copy Tip → Hub",lambda:self.copyRequested.emit(False)),
                ("Add Span",self._add),("Delete Span",self.deleteRequested.emit)):
            button=QPushButton(label);button.clicked.connect(signal);row.addWidget(button)
            if "Copy" in label:
                source,target=("Hub","Tip") if "Hub → Tip" in label else ("Tip","Hub")
                button.setToolTip(f"Overwrite {target} blade angle and thickness with {source}. Undo restores the previous values.")

    def set_sections(self,sections,index=0):
        self.combo.blockSignals(True);self.combo.clear()
        for s in sections:
            self.combo.addItem("Hub" if s.span==0 else "Tip" if s.span==1 else f"Span {s.span:.6g}")
        self.combo.setCurrentIndex(index);self.combo.blockSignals(False)

    def _add(self):
        value,ok=QInputDialog.getDouble(self,"Add Span Section","Span (0 < span < 1)",.5,.000001,.999999,6)
        if ok:self.addRequested.emit(value)
