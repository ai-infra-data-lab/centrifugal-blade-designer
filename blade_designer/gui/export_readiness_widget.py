"""Read-only export-input diagnostic panel."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QPushButton,QLabel,QPlainTextEdit
from ..fileio.export_readiness import assess_exports


class ExportReadinessWidget(QWidget):
    def __init__(self,source,parent=None):
        super().__init__(parent);self.source=source;self.result=None
        layout=QVBoxLayout(self)
        note=QLabel('設計値や出力ファイルを変更せず、選択翼列の出力条件を確認します。\n'
                    '表示は診断時のスナップショットです。編集後は再診断してください。\n'
                    '実CAD・フィレット・全面3D干渉・ANSYS Import/Meshは、この診断では実行しません。')
        note.setWordWrap(True);layout.addWidget(note)
        self.refresh_button=QPushButton('再診断 / Refresh')
        self.refresh_button.clicked.connect(self.refresh);layout.addWidget(self.refresh_button)
        self.text=QPlainTextEdit();self.text.setReadOnly(True);layout.addWidget(self.text)

    def invalidate(self):
        self.result=None;self.text.setPlainText('設計・編集対象が変わりました。再診断してください。')

    def refresh(self):
        self.result=None
        try:
            project=self.source()
            if project is None:
                self.text.setPlainText('左側で翼列を選択してから再診断してください。');return
            report=assess_exports(project)
        except (ValueError,ArithmeticError) as exc:
            self.text.setPlainText('入力を確認してください: '+str(exc));return
        self.result=report
        lines=[f'対象 / Row: {report.row_name} ({report.kind})',f'Snapshot: {report.snapshot_hash}','']
        states={'PASS':'入力OK','BLOCKED':'不可','NOT_TESTED':'未実施'}
        for route in report.routes:
            status='入力段階で出力不可' if route.status=='BLOCKED' else '入力条件OK（実機未確認）' if route.name=='Profile Points' else '入力条件OK（CAD生成は未実施）'
            lines.append(route.name+': '+status)
            lines.extend(f'  [{states[c.state]}] {c.code}: {c.message}' for c in route.checks)
            lines.append('')
        lines.append('ANSYS Import / Mesh: NOT_TESTED')
        self.text.setPlainText('\n'.join(lines))
