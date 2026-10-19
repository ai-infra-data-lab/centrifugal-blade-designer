"""Output preferences only: never stored in the design or Undo history."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QCheckBox, QDialogButtonBox, QMessageBox)
from ..fileio.coordinate_csv import COORDINATES, CoordinateCsvOptions


class CoordinateExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('座標CSV出力 / Coordinate CSV')
        layout = QVBoxLayout(self)
        note = QLabel('Z軸回り・長さ mm。θは+X基準、+Zから見て反時計回りが正。\n'
                      'θは連続角を保持。Rθ = R × θ[rad]（mm）。全周コピーは出力しません。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.preset = QComboBox()
        for label, columns in (('XYZ', ('x_mm', 'y_mm', 'z_mm')),
                               ('R / θ[deg] / Z', ('r_mm', 'theta_deg', 'z_mm')),
                               ('R / θ[rad] / Z', ('r_mm', 'theta_rad', 'z_mm')),
                               ('Rθ / Z / R', ('rtheta_mm', 'z_mm', 'r_mm'))):
            self.preset.addItem(label, columns)
        layout.addWidget(self.preset)
        layout.addWidget(QLabel('出力する列にチェック。上／下で列順を変更できます。'))
        row = QHBoxLayout()
        self.columns = QListWidget()
        row.addWidget(self.columns)
        buttons = QVBoxLayout()
        self.up = QPushButton('上へ / Up')
        self.down = QPushButton('下へ / Down')
        self.up.clicked.connect(lambda: self.move_column(-1))
        self.down.clicked.connect(lambda: self.move_column(1))
        buttons.addWidget(self.up)
        buttons.addWidget(self.down)
        buttons.addStretch()
        row.addLayout(buttons)
        layout.addLayout(row)
        self.metadata = QCheckBox('翼列・主翼/スプリッター・Span・LE/PS/TE/SS等の識別列を先頭に付ける')
        self.metadata.setChecked(True)
        layout.addWidget(self.metadata)
        self.split = QCheckBox('主翼／スプリッターのSpanごとに別CSVへ出力')
        layout.addWidget(self.split)
        layout.addWidget(QLabel('分割時は保存名の末尾に _spans を付けた新規フォルダを作成します。'))
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.preset.currentIndexChanged.connect(self.apply_preset)
        self.apply_preset()

    def apply_preset(self, *_):
        selected = self.preset.currentData()
        self.columns.clear()
        for key in (*selected, *(c for c in COORDINATES if c not in selected)):
            item = QListWidgetItem(key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if key in selected else Qt.CheckState.Unchecked)
            self.columns.addItem(item)
        self.columns.setCurrentRow(0)

    def move_column(self, direction):
        index = self.columns.currentRow()
        if 0 <= index + direction < self.columns.count():
            item = self.columns.takeItem(index)
            self.columns.insertItem(index + direction, item)
            self.columns.setCurrentRow(index + direction)

    def options(self):
        columns = tuple(self.columns.item(i).text() for i in range(self.columns.count())
                        if self.columns.item(i).checkState() == Qt.CheckState.Checked)
        result = CoordinateCsvOptions(columns, self.split.isChecked(), self.metadata.isChecked())
        result.validate()
        return result

    def accept(self):
        try:
            self.options()
        except ValueError as exc:
            QMessageBox.warning(self, '座標CSV', str(exc))
            return
        super().accept()
