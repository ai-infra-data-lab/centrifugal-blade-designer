"""Read-only, fixed-density CAD-law inspection; never a CAD validity result."""
from copy import deepcopy
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QCheckBox
from .preview_3d import Preview3D
from ..models.blade_rows import row_parameters
from ..geometry.geometry_3d import generate_impeller
from ..geometry.cad_surface_reference import reference_surfaces,reference_lines
from ..fileio.geometry_source import geometry_source
from ..fileio.trim_export_guard import guard_trim_export


class CadSurfaceReferenceWidget(QWidget):
    def __init__(self,source,parent=None):
        super().__init__(parent);self.source=source;self.result=None
        layout=QVBoxLayout(self)
        note=QLabel('CADと同じ補間・端部接線を使う、翼面だけの固定密度の参照表示です。\n'
            '実CADの自動密度選択・端面・フィレット・STEPは含みません。ANSYS未検証。')
        note.setWordWrap(True);layout.addWidget(note)
        row=QHBoxLayout();layout.addLayout(row)
        self.refresh_button=QPushButton('現在の設計を取得 / Refresh');row.addWidget(self.refresh_button)
        self.group=QComboBox();self.group.addItems(['Main','Splitter']);row.addWidget(self.group)
        row.addWidget(QLabel('補間格子'))
        self.density=QComboBox();self.density.addItems(['33','65','129','257','513']);self.density.setCurrentText('65');row.addWidget(self.density)
        self.full=QCheckBox('Full Annulus');row.addWidget(self.full);row.addStretch()
        self.info=QLabel();self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.preview=Preview3D();layout.addWidget(self.preview,1);self.preview.hide()
        self.refresh_button.clicked.connect(self.refresh)
        self.group.currentIndexChanged.connect(self._render)
        self.density.currentIndexChanged.connect(self._render)
        self.full.toggled.connect(self._annulus)

    def invalidate(self):
        self.result=None;self.preview.hide()
        self.info.setText('設計・編集対象が変わりました。現在の設計を再取得してください。')

    def refresh(self):
        self.result=None
        try:
            project=self.source()
            if project is None:raise ValueError('翼列を選択してください。')
            project=deepcopy(project);params=project
            if project.blade_rows is not None:
                row=next(r for r in project.blade_rows if r.identifier==project.active_blade_row)
                if row.kind!='impeller':raise ValueError('CAD参照はImpeller専用です。静翼CADは未対応です。')
                params=row_parameters(project,row)
            guard_trim_export(params)
            geometry=generate_impeller(params)
            source=geometry_source(project,'meridional_3d',kind='impeller')
            self.result={'geometry':geometry,'parameters':params,'source':source}
            self.group.model().item(1).setEnabled(bool(geometry.splitter_sections))
            if not geometry.splitter_sections:
                self.group.blockSignals(True);self.group.setCurrentIndex(0);self.group.blockSignals(False)
            self._render()
        except (ValueError,ArithmeticError) as exc:
            self.result=None;self.preview.hide();self.info.setText('参照面を作成できません: '+str(exc))

    def _render(self,*_):
        if self.result is None:return
        try:
            geometry=self.result['geometry'];params=self.result['parameters'];source=self.result['source']
            sections=geometry.sections if self.group.currentIndex()==0 else geometry.splitter_sections
            if not sections:raise ValueError('Splitterがありません。')
            density=int(self.density.currentText())
            surfaces=reference_surfaces(sections,params.sections,density)
            lines=reference_lines(surfaces,[s.span for s in sections])
            self.preview.update_surface_reference(lines,f'{source.row_name} • CAD reference • {self.group.currentText()} • grid {density}')
            self._annulus();self.preview.show()
            self.info.setText(f'{source.row_name} / {self.group.currentText()} / grid {density} / mm / Z axis\nSnapshot: {source.snapshot_hash}\n'
                '現在の設計を取得した時点の参照面。BREP・全面偏差・干渉・Import/Meshの合否ではありません。')
        except (ValueError,ArithmeticError) as exc:
            self.result=None;self.preview.hide();self.info.setText('参照面を表示できません: '+str(exc))

    def _annulus(self,*_):
        if self.result is not None:self.preview.set_full_annulus(self.full.isChecked(),self.result['parameters'].geometry.vane_count)
