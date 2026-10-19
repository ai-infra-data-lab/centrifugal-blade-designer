"""Output preferences only: never stored in the design or Undo history."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QCheckBox, QDialogButtonBox, QMessageBox)
from ..fileio.coordinate_csv import COORDINATES, CoordinateCsvOptions


class CoordinateExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('座標出力 / Coordinate CSV・TXT')
        layout = QVBoxLayout(self)
        note = QLabel('Z軸回り・長さ mm。θは+X基準、+Zから見て反時計回りが正。\n'
                      'θは連続角を保持。Rθ = R × θ[rad]（mm）。全周コピーは出力しません。')
        note.setWordWrap(True)
        layout.addWidget(note)
        targets = QHBoxLayout()
        self.blades = QCheckBox('翼（Main / Splitter）')
        self.blades.setChecked(True)
        self.hub = QCheckBox('Hub')
        self.shroud = QCheckBox('Shroud')
        for box in (self.blades, self.hub, self.shroud):
            targets.addWidget(box)
        layout.addLayout(targets)
        layout.addWidget(QLabel('Hub / Shroud：選択翼列の所属区間の子午線（θ=0）を出力します。'))
        self.wall_layout = QComboBox()
        for label, key in (('翼・Hub・Shroudを1ファイルにまとめる', 'combined'),
                           ('翼とは別にHub＋Shroudを1ファイルにまとめる', 'together'),
                           ('Hub・Shroudをそれぞれ別ファイルにする', 'separate')):
            self.wall_layout.addItem(label, key)
        layout.addWidget(self.wall_layout)
        self.shroud_source=QComboBox()
        for label,key in (('Shroud：図面用','drawing'),('Shroud：解析用','analysis'),('Shroud：図面用と解析用の両方','both')):
            self.shroud_source.addItem(label,key)
        layout.addWidget(self.shroud_source)
        self.extension = QComboBox()
        self.extension.addItem('CSV (.csv) — カンマ区切り', 'csv')
        self.extension.addItem('TXT (.txt) — タブ区切り', 'txt')
        layout.addWidget(self.extension)
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
        self.metadata = QCheckBox('翼列・Main/Splitter・Span・LE/PS/TE/SS・Hub/Shroudの識別列を付ける')
        self.metadata.setChecked(True)
        layout.addWidget(self.metadata)
        self.split = QCheckBox('主翼／スプリッターのSpanごとに別ファイルへ出力')
        layout.addWidget(self.split)
        layout.addWidget(QLabel('分割時：新規フォルダ _spans（Span分割）または _files（壁面分割）に保存。'))
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.preset.currentIndexChanged.connect(self.apply_preset)
        for box in (self.blades, self.hub, self.shroud):
            box.toggled.connect(self.sync_layout)
        self.wall_layout.currentIndexChanged.connect(self.sync_layout)
        self.apply_preset()
        self.sync_layout()

    def sync_layout(self, *_):
        walls = self.hub.isChecked() or self.shroud.isChecked()
        self.wall_layout.setEnabled(walls)
        allowed = self.blades.isChecked() and (not walls or self.wall_layout.currentData() != 'combined')
        self.split.setEnabled(allowed)
        if not allowed:
            self.split.setChecked(False)

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
        result = CoordinateCsvOptions(columns, self.split.isChecked(), self.metadata.isChecked(),
                                      self.blades.isChecked(), self.hub.isChecked(), self.shroud.isChecked(),
                                      self.wall_layout.currentData(), self.extension.currentData(),self.shroud_source.currentData())
        result.validate()
        return result

    def accept(self):
        try:
            self.options()
        except ValueError as exc:
            QMessageBox.warning(self, '座標CSV', str(exc))
            return
        super().accept()
