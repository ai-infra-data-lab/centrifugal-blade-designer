"""Separate coordinate-study workspace; ordinary design and legacy optimizer stay intact."""
from dataclasses import replace
from pathlib import Path
import csv
import uuid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QCheckBox,
    QSpinBox, QLineEdit, QComboBox, QFileDialog, QAbstractItemView)

from .control_point_editor import CompactDoubleSpinBox
from .coordinate_export_dialog import CoordinateExportDialog
from .coordinate_study_worker import CoordinateStudyWorker
from ..optimization.coordinate_parameters import CoordinateStudy
from ..fileio.coordinate_csv import CoordinateCsvOptions
from ..fileio.coordinate_study import queue_study, read_study, import_results, rank_results, project_hash, digest, json_bytes, file_sha256


class CoordinateStudyDialog(QDialog):
    def __init__(self, capture, apply, parent=None):
        super().__init__(parent)
        self.setWindowTitle('座標最適化 / Coordinate Study — External Evaluation')
        self.resize(1150, 820)
        self.capture_design = capture
        self.apply_design = apply
        self.worker = None
        self._closing = False
        self.study = None
        self.manifest = None
        self.results = {}
        self.source_directory = None
        self.results_path = None
        self.results_hash = None
        self.options = CoordinateCsvOptions(include_hub=True, include_shroud=True, wall_layout='separate')
        layout = QVBoxLayout(self)
        self.note = QLabel('基準設計＋差分パラメータ → 複数翼列の断面／壁面座標 → 外部解析結果。\n'
                           '3D面・CAD・CFD評価は実行しません。Shroud等は座標出力設定で選択します。')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        top = QHBoxLayout()
        self.capture_button = QPushButton('現在の設計を移行 / Capture Baseline')
        self.capture_button.clicked.connect(self.capture)
        self.settings_button = QPushButton('座標出力設定 / CSV・TXT')
        self.settings_button.clicked.connect(self.settings)
        self.open_button = QPushButton('保存済みStudyを開く')
        self.open_button.clicked.connect(self.open_run)
        for button in (self.capture_button, self.settings_button, self.open_button):
            top.addWidget(button)
        layout.addLayout(top)
        self.rows = QListWidget()
        self.rows.setMaximumHeight(90)
        self.rows.itemChanged.connect(self.reset_rows)
        layout.addWidget(self.rows)
        self.variables_table = QTableWidget(0, 5)
        self.variables_table.setHorizontalHeaderLabels(['使用', '差分パラメータ（初期値0）', '下限', '上限', '連動グループ'])
        self.variables_table.setColumnWidth(0, 55)
        self.variables_table.setColumnWidth(1, 650)
        layout.addWidget(self.variables_table, 2)
        actions = QHBoxLayout()
        self.count = QSpinBox()
        self.count.setRange(0, 1000)
        self.count.setValue(8)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.export_button = QPushButton('基準＋候補を出力 / LHS')
        self.local_button = QPushButton('選択候補の近傍を出力 / Local LHS')
        self.cancel_button = QPushButton('取消')
        self.cancel_button.setEnabled(False)
        self.export_button.clicked.connect(lambda: self.export(False))
        self.local_button.clicked.connect(lambda: self.export(True))
        self.cancel_button.clicked.connect(lambda: self.worker.cancel() if self.worker else None)
        actions.addWidget(QLabel('候補数（＋基準1）'))
        actions.addWidget(self.count)
        actions.addWidget(QLabel('Seed'))
        actions.addWidget(self.seed)
        for button in (self.export_button, self.local_button, self.cancel_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        proposals = QHBoxLayout()
        self.proposal_button = QPushButton('外部結果から次候補を出力 / RBF')
        self.proposal_button.setToolTip('1〜50候補。解析条件IDと十分な成功データが必要。予測は外部解析値ではありません。')
        self.proposal_button.clicked.connect(lambda: self.export(proposal=True))
        proposals.addWidget(self.proposal_button)
        self.proposal_note = QLabel()
        self.proposal_note.setWordWrap(True)
        proposals.addWidget(self.proposal_note)
        layout.addLayout(proposals)
        context = QHBoxLayout()
        self.evaluation_context = QLineEdit()
        self.evaluation_context.setMaxLength(512)
        self.evaluation_context.setPlaceholderText('例：回転数・入口条件・評価作動点を識別するケース名。未指定時は条件の一致を検査できません。')
        context.addWidget(QLabel('外部解析条件ID'))
        context.addWidget(self.evaluation_context)
        layout.addLayout(context)
        evaluation = QHBoxLayout()
        self.import_button = QPushButton('外部結果CSVを取込')
        self.import_button.clicked.connect(self.import_csv)
        self.objective = QLineEdit('efficiency')
        self.direction = QComboBox()
        self.direction.addItems(['最大化', '最小化'])
        self.constraint_name = QLineEdit()
        self.constraint_name.setPlaceholderText('任意：制約の評価列名')
        self.minimum = QLineEdit()
        self.minimum.setPlaceholderText('下限（空欄で未指定）')
        self.maximum = QLineEdit()
        self.maximum.setPlaceholderText('上限（空欄で未指定）')
        rank = QPushButton('順位を更新')
        rank.clicked.connect(self.refresh_cases)
        self.apply_button = QPushButton('選択候補を通常設計へ適用')
        self.apply_button.clicked.connect(self.apply_selected)
        for widget in (self.import_button, QLabel('目的列'), self.objective, self.direction, rank, self.apply_button):
            evaluation.addWidget(widget)
        layout.addLayout(evaluation)
        limits = QHBoxLayout()
        for widget in (QLabel('外部評価の制約'), self.constraint_name, self.minimum, self.maximum):
            limits.addWidget(widget)
        layout.addLayout(limits)
        self.cases_table = QTableWidget(0, 5)
        self.cases_table.setHorizontalHeaderLabels(['候補ID', '座標出力', '外部評価', '目的値', '予測値（未評価）'])
        self.cases_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cases_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cases_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cases_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.cases_table, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.capture()

    @property
    def busy(self):
        return self.worker is not None and not self.worker._completed

    def error(self, exc):
        self.status.setText(str(exc))

    def capture(self):
        if self.busy:
            return
        try:
            self.study = CoordinateStudy(self.capture_design())
            self.manifest = None
            self.results = {}
            self.source_directory = self.results_path = self.results_hash = None
            self.rows.blockSignals(True)
            self.rows.clear()
            for row in self.study.baseline.blade_rows:
                item = QListWidgetItem(f'{row.name} ({row.kind})')
                item.setData(Qt.ItemDataRole.UserRole, row.identifier)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.rows.addItem(item)
            self.rows.blockSignals(False)
            self.fill_variables()
            self.cases_table.setRowCount(0)
            self.status.setText('移行完了：差分0は元の制御点・設計値を保持します。'
                                '子午面変更時は所属区間内のLE/TE相対位置を保持します。')
        except (ValueError, ArithmeticError) as exc:
            self.error(exc)

    def reset_rows(self):
        if self.busy or self.study is None:
            return
        selected = [self.rows.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.rows.count())
                    if self.rows.item(i).checkState() == Qt.CheckState.Checked]
        if not selected:
            self.variables_table.setRowCount(0)
            self.status.setText('対象翼列を1つ以上選択してください。')
            return
        self.study = CoordinateStudy(self.study.baseline, selected)
        self.manifest = None
        self.results = {}
        self.source_directory = self.results_path = self.results_hash = None
        self.cases_table.setRowCount(0)
        self.fill_variables()

    def fill_variables(self, variables=None):
        self.parameter_rows = []
        self.variables_table.setRowCount(len(self.study.variables))
        supplied = {v.key: v for v in variables or self.study.variables}
        for index, original in enumerate(self.study.variables):
            variable = supplied.get(original.key, replace(original, enabled=False))
            use = QCheckBox()
            use.setChecked(variable.enabled)
            self.variables_table.setCellWidget(index, 0, use)
            item = QTableWidgetItem(variable.label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.variables_table.setItem(index, 1, item)
            boxes = []
            for column, value in ((2, variable.lower), (3, variable.upper)):
                box = CompactDoubleSpinBox()
                box.setDecimals(10)
                box.setRange(-1e9, 1e9)
                box.setValue(value)
                self.variables_table.setCellWidget(index, column, box)
                boxes.append(box)
            link = QLineEdit(variable.link)
            link.setPlaceholderText('同じ名前で同じ差分を連動')
            self.variables_table.setCellWidget(index, 4, link)
            self.parameter_rows.append((variable, use, *boxes, link))
            use.toggled.connect(self.update_proposal_hint)
            for box in boxes:box.valueChanged.connect(self.update_proposal_hint)
            link.textChanged.connect(self.update_proposal_hint)
        self.update_proposal_hint()

    def update_proposal_hint(self, *_):
        try:
            active = self.study.validate_variables(self.variables())
            dimensions = len({('link', v.link) if v.link else ('key', v.key) for v in active})
            self.proposal_note.setText(f'独立{dimensions}変数：成功評価が{max(8, 2*dimensions+4)}点以上必要。予測は未評価。'
                                      if dimensions else '使用する変数を選択してください。予測は未評価。')
        except ValueError:
            self.proposal_note.setText('変数設定を確認してください。予測は未評価です。')

    def variables(self):
        return [replace(v, enabled=use.isChecked(), lower=low.value(), upper=high.value(), link=link.text().strip())
                for v, use, low, high, link in self.parameter_rows]

    def settings(self):
        dialog = CoordinateExportDialog(self)
        for control, value in ((dialog.blades, self.options.include_blades), (dialog.hub, self.options.include_hub),
                               (dialog.shroud, self.options.include_shroud), (dialog.metadata, self.options.include_metadata),
                               (dialog.split, self.options.split_spans)):
            control.setChecked(value)
        for control, value in ((dialog.wall_layout, self.options.wall_layout),
                               (dialog.shroud_source, self.options.shroud_source), (dialog.extension, self.options.extension)):
            control.setCurrentIndex(control.findData(value))
        dialog.columns.clear()
        from ..fileio.coordinate_csv import COORDINATES
        for name in (*self.options.columns, *(c for c in COORDINATES if c not in self.options.columns)):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in self.options.columns else Qt.CheckState.Unchecked)
            dialog.columns.addItem(item)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options()

    def selected_case(self):
        if self.manifest is None or self.cases_table.currentRow() < 0:
            raise ValueError('生成済み候補を選択してください。')
        key = self.cases_table.item(self.cases_table.currentRow(), 0).text()
        return next(case for case in self.manifest['cases'] if case['candidate_id'] == key)

    def export(self, local=False, proposal=False):
        try:
            if self.busy or self.study is None:
                return
            selected = [self.rows.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.rows.count())
                        if self.rows.item(i).checkState() == Qt.CheckState.Checked]
            if not selected:
                raise ValueError('対象翼列を選択してください。')
            center = self.selected_case()['values'] if local else None
            if local and self.selected_case()['status'] != 'READY_FOR_EXTERNAL':
                raise ValueError('座標が成立した候補だけを近傍探索に使用できます。')
            specification = None
            if proposal:
                if self.manifest is None or self.results_path is None or not self.results:
                    raise ValueError('先にStudyを開き、外部評価CSVを取り込んでください。')
                name = self.constraint_name.text().strip()
                constraints = ({name: tuple(float(edit.text()) if edit.text().strip() else None
                                           for edit in (self.minimum, self.maximum))} if name else {})
                specification = {'source_directory': str(self.source_directory),
                                 'manifest_hash': digest(json_bytes(self.manifest)),
                                 'results_path': str(self.results_path), 'results_hash': self.results_hash,
                                 'objective': self.objective.text().strip(),
                                 'maximize': self.direction.currentIndex() == 0, 'constraints': constraints}
            path = QFileDialog.getSaveFileName(self, '新しいStudyフォルダ名を指定', f'coordinate-study-{uuid.uuid4().hex[:8]}')[0]
            if not path:
                return
            if Path(path).exists():
                raise FileExistsError('既存フォルダは上書きしません。新しい名前を指定してください。')
            job = queue_study(self.study, self.variables(), self.count.value(), self.seed.value(),
                              self.options, path, center, evaluation_context=self.evaluation_context.text().strip(),
                              proposal=specification)
            worker = CoordinateStudyWorker(job, QApplication.instance())
            self.worker = worker
            worker.progress.connect(self.status.setText)
            worker.completed.connect(self._worker_finished)
            worker.completed.connect(worker.deleteLater)
            self.destroyed.connect(worker.cancel)
            self.set_busy(True)
            worker.start()
        except (ValueError, ArithmeticError, OSError) as exc:
            self.error(exc)

    def set_busy(self, busy):
        for widget in (self.capture_button, self.settings_button, self.open_button, self.rows,
                       self.variables_table, self.count, self.seed, self.export_button,
                       self.local_button, self.proposal_button, self.import_button, self.apply_button, self.evaluation_context):
            widget.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    def _worker_finished(self, report):
        worker = self.worker
        self.worker = None
        self.set_busy(False)
        if worker is not None:
            worker.deleteLater()
        if report.get('overall') == 'PASS':
            try:
                self.study, self.manifest = read_study(report['directory'])
                self.results = {}
                self.source_directory = Path(report['directory'])
                self.results_path = self.results_hash = None
                self.refresh_cases()
                summary = self.status.text() if self.manifest.get('proposal') else ''
                self.status.setText('出力完了：' + report['directory'] + '\n外部解析を行い、結果CSVを取り込んでください。'
                                    + ('\n' + summary if summary else ''))
            except (OSError, ValueError, KeyError) as exc:
                self.error(exc)
        else:
            self.status.setText(report.get('error', {}).get('message', '取消／出力失敗'))
        if self._closing:
            QTimer.singleShot(0, self.close)

    def open_run(self):
        directory = QFileDialog.getExistingDirectory(self, 'Studyフォルダを選択')
        if not directory:
            return
        try:
            from ..optimization.coordinate_parameters import CoordinateVariable
            study, manifest = read_study(directory)
            self.study = study
            self.manifest = manifest
            self.results = {}
            self.source_directory = Path(directory)
            self.results_path = self.results_hash = None
            self.rows.blockSignals(True)
            self.rows.clear()
            for row in study.baseline.blade_rows:
                item = QListWidgetItem(f'{row.name} ({row.kind})')
                item.setData(Qt.ItemDataRole.UserRole, row.identifier)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if row.identifier in study.row_ids else Qt.CheckState.Unchecked)
                self.rows.addItem(item)
            self.rows.blockSignals(False)
            self.fill_variables([CoordinateVariable(**v) for v in manifest['variables']])
            self.options = CoordinateCsvOptions(**{**manifest['options'], 'columns': tuple(manifest['options']['columns'])})
            self.evaluation_context.setText(manifest.get('evaluation_context', ''))
            self.refresh_cases()
            summary = self.status.text() if self.manifest.get('proposal') else ''
            self.status.setText('Studyを再開しました。外部結果CSVを取り込めます。' + ('\n' + summary if summary else ''))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.error(exc)

    def import_csv(self):
        if self.manifest is None:
            self.status.setText('先に候補を出力するかStudyを開いてください。')
            return
        path = QFileDialog.getOpenFileName(self, '外部結果CSV', '', 'CSV (*.csv)')[0]
        if path:
            try:
                before_hash = file_sha256(path)
                imported = import_results(path, self.manifest)
                after_hash = file_sha256(path)
                if before_hash != after_hash:
                    raise ValueError('外部CSVが取込中に変更されました。再度取り込んでください。')
                self.results = imported
                self.results_path = Path(path)
                self.results_hash = after_hash
                self.refresh_cases()
            except (OSError, ValueError, csv.Error) as exc:
                self.error(exc)

    def refresh_cases(self):
        if self.manifest is None:
            return
        try:
            constraints = {}
            name = self.constraint_name.text().strip()
            if name:
                constraints[name] = tuple(float(edit.text()) if edit.text().strip() else None
                                          for edit in (self.minimum, self.maximum))
            ranked = rank_results(self.results, self.objective.text().strip(), self.direction.currentIndex() == 0, constraints)
            cases = {case['candidate_id']: case for case in self.manifest['cases']}
            order = ranked + [key for key in cases if key not in ranked]
            self.cases_table.setRowCount(len(order))
            prediction_objective = (self.manifest['proposal']['objective']
                                    if self.manifest.get('sampling') == 'rbf_external' else None)
            self.cases_table.horizontalHeaderItem(4).setText(
                f'予測 {prediction_objective}（未評価）' if prediction_objective else '予測値（未評価）')
            for row, key in enumerate(order):
                result = self.results.get(key, {'status': 'pending', 'metrics': {}})
                metric = result['metrics'].get(self.objective.text().strip())
                coordinate_status = '座標出力済み' if cases[key]['status'] == 'READY_FOR_EXTERNAL' else '座標生成エラー'
                external_status = {'pending': '未評価', 'success': '成功', 'failed': '解析失敗'}[result['status']]
                predicted = (cases[key].get('prediction', {}).get('metrics', {}).get(prediction_objective)
                             if prediction_objective else None)
                for column, value in enumerate((key, coordinate_status, external_status, '' if metric is None else f'{metric:.12g}',
                                                '' if predicted is None else f'{predicted:.12g}')):
                    item = QTableWidgetItem(value)
                    item.setToolTip(cases[key].get('error', ''))
                    self.cases_table.setItem(row, column, item)
            self.status.setText(f'外部評価・制約による採用可能候補：{len(ranked)} / {len(cases)}。'
                                '未取得／失敗は順位に含めません。近傍LHSは局所候補生成です。')
            if prediction_objective:
                proposal = self.manifest['proposal']
                error = proposal['validation_metrics'][prediction_objective]['cv_rmse']
                self.status.setText(self.status.text() + f'\nRBF：実評価{proposal["training_count"]}点、'
                                    f'独立{proposal["independent_dimensions"]}変数、4分割検証RMSE {error:.6g} '
                                    f'（{prediction_objective}の単位）。予測は実解析値・成立保証ではありません。')
        except ValueError as exc:
            self.error(exc)

    def apply_selected(self):
        try:
            case = self.selected_case()
            if case['status'] != 'READY_FOR_EXTERNAL':
                raise ValueError('座標生成に失敗した候補は適用できません。')
            candidate = self.study.candidate(case['values'])
            if project_hash(candidate) != case['candidate_hash']:
                raise ValueError('Candidate snapshot mismatch.')
            self.apply_design(candidate, project_hash(self.study.baseline))
            self.status.setText('候補を通常設計へ適用しました。外部解析結果の妥当性を保証する操作ではありません。')
        except (ValueError, ArithmeticError) as exc:
            self.error(exc)

    def closeEvent(self, event):
        if self.busy:
            self._closing = True
            event.ignore()
            self.worker.cancel()
            return
        super().closeEvent(event)
