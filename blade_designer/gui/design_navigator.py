"""Vertical design selection and blade-row management."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QComboBox, QLabel, QDialog, QFormLayout, QLineEdit, QDialogButtonBox)


class DesignNavigator(QWidget):
    meridionalSelected = Signal()
    rowSelected = Signal(str)
    addRequested = Signal(str, str)
    renameRequested = Signal(str, str)
    deleteRequested = Signal()
    moveRequested = Signal(int)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(180)
        self.setMaximumWidth(220)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("編集対象 / Design"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.meridional_item = QTreeWidgetItem(self.tree, ["子午面 / Meridional"])
        self.rows_item = QTreeWidgetItem(self.tree, ["翼 / Blade Rows"])
        self.rows_item.setExpanded(True)
        self.tree.currentItemChanged.connect(self._selected)
        self.tree.itemClicked.connect(self._clicked)
        layout.addWidget(self.tree, 1)
        self.add_button = QPushButton("追加 / Add Row")
        self.rename_button = QPushButton("名前変更 / Rename")
        self.delete_button = QPushButton("削除 / Delete")
        self.up_button = QPushButton("上へ / Up")
        self.down_button = QPushButton("下へ / Down")
        for button in (self.add_button, self.rename_button, self.delete_button, self.up_button, self.down_button):
            layout.addWidget(button)
        self.add_button.clicked.connect(self._request_add)
        self.rename_button.clicked.connect(self._request_rename)
        self.delete_button.clicked.connect(self.deleteRequested)
        self.up_button.clicked.connect(lambda: self.moveRequested.emit(-1))
        self.down_button.clicked.connect(lambda: self.moveRequested.emit(1))
        self.delete_button.setToolTip("Keep at least one blade row. Undo restores a deleted row.")
        self.up_button.setToolTip("Change list order without moving blade endpoints.")
        self.down_button.setToolTip(self.up_button.toolTip())

    def _request_add(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("翼列を追加 / Add Blade Row")
        dialog.setModal(True)
        form = QFormLayout(dialog)
        dialog.name_edit = QLineEdit()
        dialog.kind_combo = QComboBox()
        dialog.kind_combo.addItem("インペラ / Impeller", "impeller")
        dialog.kind_combo.addItem("静翼 / Diffuser", "diffuser")
        dialog.kind_combo.addItem('翼なし子午面 / Meridional only','meridional')
        form.addRow("名前 / Name", dialog.name_edit)
        form.addRow("種類 / Type", dialog.kind_combo)
        dialog.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("追加 / Add")
        ok.setEnabled(False)
        dialog.name_edit.textChanged.connect(lambda text: ok.setEnabled(bool(text.strip())))
        dialog.buttons.accepted.connect(dialog.accept)
        dialog.buttons.rejected.connect(dialog.reject)
        dialog.accepted.connect(lambda: self.addRequested.emit(dialog.kind_combo.currentData(), dialog.name_edit.text().strip()))
        dialog.finished.connect(dialog.deleteLater)
        form.addRow(dialog.buttons)
        self.add_dialog = dialog
        dialog.open()
        dialog.name_edit.setFocus()

    def _request_rename(self):
        item = self.tree.currentItem()
        if item is None or item.parent() is not self.rows_item: return
        identifier = item.data(0, Qt.ItemDataRole.UserRole)
        dialog = QDialog(self)
        dialog.setWindowTitle("翼列の名前変更 / Rename Blade Row")
        dialog.setModal(True)
        form = QFormLayout(dialog)
        dialog.name_edit = QLineEdit(item.text(0))
        form.addRow("名前 / Name", dialog.name_edit)
        dialog.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("変更 / Rename")
        dialog.name_edit.textChanged.connect(lambda text: ok.setEnabled(bool(text.strip())))
        dialog.buttons.accepted.connect(dialog.accept)
        dialog.buttons.rejected.connect(dialog.reject)
        dialog.accepted.connect(lambda: self.renameRequested.emit(identifier, dialog.name_edit.text().strip()))
        dialog.finished.connect(dialog.deleteLater)
        form.addRow(dialog.buttons)
        self.rename_dialog = dialog
        dialog.open()
        dialog.name_edit.selectAll()
        dialog.name_edit.setFocus()

    def set_rows(self, rows, identifier, select_row=False):
        self.rows_item.setText(0,'要素 / Elements' if any(row.kind=='meridional' for row in rows) else '翼 / Blade Rows')
        self.active_identifier = identifier
        meridional = self.tree.currentItem() is self.meridional_item and not select_row
        self.tree.blockSignals(True)
        try:
            existing = [self.rows_item.child(index) for index in range(self.rows_item.childCount())]
            if [item.data(0, Qt.ItemDataRole.UserRole) for item in existing] != [row.identifier for row in rows]:
                self.rows_item.takeChildren()
                existing = [QTreeWidgetItem(self.rows_item) for row in rows]
            for row, item in zip(rows, existing):
                item.setText(0, row.name)
                item.setData(0, Qt.ItemDataRole.UserRole, row.identifier)
                item.setToolTip(0, row.kind.title())
                if row.identifier == identifier and not meridional:
                    self.tree.setCurrentItem(item)
            self.rows_item.setExpanded(True)
        finally:
            self.tree.blockSignals(False)
        self._buttons()

    def _buttons(self):
        item = self.tree.currentItem()
        index = self.rows_item.indexOfChild(item) if item is not None else -1
        count = self.rows_item.childCount()
        self.rename_button.setEnabled(index >= 0)
        self.delete_button.setEnabled(index >= 0 and count > 1)
        self.up_button.setEnabled(index > 0)
        self.down_button.setEnabled(index >= 0 and index < count - 1)

    def _selected(self, item, previous):
        self._buttons()
        if item is self.meridional_item:
            self.meridionalSelected.emit()
        elif item is self.rows_item:
            self.rowSelected.emit(self.active_identifier)
        elif item is not None and item.parent() is self.rows_item:
            self.rowSelected.emit(item.data(0, Qt.ItemDataRole.UserRole))

    def _clicked(self, item, column):
        # Clicking the already selected legacy row also enters row management.
        item = self.tree.currentItem()
        if item is not None and item.parent() is self.rows_item:
            self.rowSelected.emit(item.data(0, Qt.ItemDataRole.UserRole))
