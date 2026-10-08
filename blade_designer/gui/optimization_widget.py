from copy import deepcopy
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,
    QTreeWidget,QTreeWidgetItem,QCheckBox,QLineEdit,QTabWidget,QTableWidget,QPlainTextEdit)
from ..models.parameters import BladeParameters
from ..models.validation import validate_parameters,ValidationLevel
from ..optimization.models import (OptimizationParameter,ParameterType,ValueMode,OptimizationMode,
    GeometryConstraints,CandidateResult)
from ..optimization.presets import default_parameters,GROUPS
from ..optimization.parameter_mapper import ParameterMapper
from ..optimization.feasibility import evaluate_candidate
from .control_point_editor import CompactDoubleSpinBox
from .plot_widgets import configure_plot,COLORS

CONSTRAINT_LABELS = {
    "minimum_thickness":"Minimum thickness [mm]",
    "maximum_curvature":"Maximum PS/SS curvature [1/mm]",
    "minimum_curvature_radius":"Minimum PS/SS curvature radius [mm]",
    "minimum_throat":"Minimum throat [mm]",
    "maximum_throat":"Maximum throat [mm]",
    "minimum_te_thickness":"Minimum TE thickness [mm]",
    "maximum_turning_gradient":"Maximum |dβm/dMnorm| [deg]",
    "maximum_turning_second_derivative":"Maximum |d²βm/dMnorm²| [deg]",
}


class OptimizationWidget(QWidget):
    captureRequested = Signal()
    applyRequested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._baseline = BladeParameters()
        self._loading = False
        self.rows: list[dict] = []
        self.last_result: CandidateResult | None = None
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("Geometry Optimization",OptimizationMode.GEOMETRY.value)
        self.mode.addItem("Architecture Optimization",OptimizationMode.ARCHITECTURE.value)
        self.preset = QComboBox()
        self.preset.addItems(["9-variable set","7-variable compact set"])
        self.capture_button = QPushButton("Capture Current Design as Baseline")
        self.capture_button.clicked.connect(self.captureRequested)
        toolbar.addWidget(self.mode)
        toolbar.addWidget(self.preset)
        toolbar.addWidget(self.capture_button)
        layout.addLayout(toolbar)
        self.baseline_label = QLabel()
        self.baseline_label.setWordWrap(True)
        layout.addWidget(self.baseline_label)
        self.settings_tabs = QTabWidget()
        self.tree = QTreeWidget()
        self.tree.setColumnCount(9)
        self.tree.setHeaderLabels(["Parameter","Use","Type","Mode","Min","Initial","Max","Scale","Choices"])
        for column,width in enumerate((170,45,100,90,85,85,85,70,115)):
            self.tree.setColumnWidth(column,width)
        self.settings_tabs.addTab(self.tree,"Optimization Variables")
        constraints_page = QWidget()
        constraint_layout = QVBoxLayout(constraints_page)
        self.no_intersection = QCheckBox("No self intersection")
        self.no_intersection.setChecked(True)
        constraint_layout.addWidget(self.no_intersection)
        self.constraint_table = QTableWidget(len(CONSTRAINT_LABELS),3)
        self.constraint_table.setHorizontalHeaderLabels(["Use","Geometry constraint","Limit"])
        self.constraint_table.setColumnWidth(0,45)
        self.constraint_table.setColumnWidth(1,370)
        self.constraint_table.horizontalHeader().setStretchLastSection(True)
        constraint_layout.addWidget(self.constraint_table)
        self.constraint_controls = {}
        defaults = GeometryConstraints()
        for row,(name,label) in enumerate(CONSTRAINT_LABELS.items()):
            use = QCheckBox()
            value = self._spin()
            value.setRange(0.,1e12)
            default = getattr(defaults,name)
            use.setChecked(default is not None)
            value.setValue(default if default is not None else 100.)
            value.setEnabled(use.isChecked())
            from PySide6.QtWidgets import QTableWidgetItem
            self.constraint_table.setCellWidget(row,0,use)
            self.constraint_table.setItem(row,1,QTableWidgetItem(label))
            self.constraint_table.setCellWidget(row,2,value)
            use.toggled.connect(value.setEnabled)
            use.toggled.connect(self._invalidate)
            value.valueChanged.connect(self._invalidate)
            self.constraint_controls[name] = (use,value)
        self.no_intersection.toggled.connect(self._invalidate)
        self.settings_tabs.addTab(constraints_page,"Geometry Constraints")
        self.settings_tabs.setMinimumHeight(200)
        self.settings_tabs.setMaximumHeight(300)
        layout.addWidget(self.settings_tabs)
        actions = QHBoxLayout()
        self.preview_button = QPushButton("Generate / Check Initial Candidate")
        self.apply_button = QPushButton("Apply Feasible Candidate to Design")
        self.preview_button.clicked.connect(self.preview_candidate)
        self.apply_button.clicked.connect(self.apply_candidate)
        self.apply_button.setEnabled(False)
        actions.addWidget(self.preview_button)
        actions.addWidget(self.apply_button)
        layout.addLayout(actions)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(110)
        layout.addWidget(self.report)
        self.plot = pg.PlotWidget(background="#101c2b")
        self.plot.setMinimumHeight(200)
        self.plot.setAspectLocked(True)
        configure_plot(self.plot,"X [mm]","Y [mm]")
        self.plot.addLegend(labelTextColor="#d1dae7")
        self.curves = {name:self.plot.plot(pen=pg.mkPen(color,width=2),name=name) for name,color in COLORS.items()}
        layout.addWidget(self.plot,1)
        self.mode.currentIndexChanged.connect(self._reset_parameters)
        self.preset.currentIndexChanged.connect(self._reset_parameters)
        self._reset_parameters()

    @property
    def baseline(self) -> BladeParameters:
        return deepcopy(self._baseline)

    def _spin(self) -> CompactDoubleSpinBox:
        spin = CompactDoubleSpinBox()
        spin.setDecimals(10)
        spin.setRange(-1e12,1e12)
        spin.setSingleStep(.1)
        return spin

    def set_baseline(self, design: BladeParameters) -> None:
        errors = [i for i in validate_parameters(design) if i.level == ValidationLevel.ERROR]
        if errors:
            raise ValueError("; ".join(i.message for i in errors))
        self._baseline = deepcopy(design)
        self._reset_parameters()

    def _reset_parameters(self) -> None:
        self._loading = True
        try:
            self.tree.clear()
            self.rows = []
            mode = OptimizationMode(self.mode.currentData())
            groups = {name:QTreeWidgetItem(self.tree,[name]) for name in GROUPS}
            parameters = default_parameters(self._baseline,self.preset.currentIndex()==1,mode)
            for parameter in parameters:
                item = QTreeWidgetItem(groups[parameter.group],[parameter.name])
                row = {"parameter":deepcopy(parameter),"item":item}
                use = QCheckBox()
                use.setChecked(parameter.enabled)
                self.tree.setItemWidget(item,1,use)
                row["enabled"] = use
                for column,key,enum,initial in ((2,"type",ParameterType,parameter.parameter_type),(3,"mode",ValueMode,parameter.value_mode)):
                    combo = QComboBox()
                    for option in enum: combo.addItem(option.value,option.value)
                    combo.setCurrentIndex(combo.findData(initial.value))
                    combo.currentIndexChanged.connect(self._invalidate)
                    self.tree.setItemWidget(item,column,combo)
                    row[key] = combo
                for column,key in ((4,"lower"),(5,"initial"),(6,"upper"),(7,"scale")):
                    spin = self._spin()
                    spin.setValue(getattr(parameter,key))
                    spin.valueChanged.connect(self._invalidate)
                    self.tree.setItemWidget(item,column,spin)
                    row[key] = spin
                choices = QLineEdit(", ".join(str(v) for v in parameter.choices))
                choices.setPlaceholderText("17, 18, 19")
                choices.textChanged.connect(self._invalidate)
                self.tree.setItemWidget(item,8,choices)
                row["choices"] = choices
                choices.setEnabled(parameter.parameter_type == ParameterType.DISCRETE)
                row["type"].currentIndexChanged.connect(
                    lambda _index, combo=row["type"], editor=choices:
                    editor.setEnabled(combo.currentData() == ParameterType.DISCRETE.value))
                use.toggled.connect(self._invalidate)
                self.rows.append(row)
            if mode == OptimizationMode.GEOMETRY:
                QTreeWidgetItem(groups["Vane Arrangement"],["Vane Count = fixed baseline"])
                QTreeWidgetItem(groups["Global Geometry"],["R LE / R TE = fixed baseline"])
            self.tree.expandAll()
            g = self._baseline.geometry
            self.baseline_label.setText(
                f"Captured baseline: R LE {g.r_le:g} / R TE {g.r_te:g} mm, {g.vane_count} vanes. "
                "Capture resets the parameter set; ordinary design edits do not change this baseline. "
                "Ellipse-ratio variables require an Elliptical baseline edge.")
        finally:
            self._loading = False
        self._invalidate()

    def _invalidate(self) -> None:
        if self._loading:
            return
        self.last_result = None
        self.apply_button.setEnabled(False)
        self.report.setPlainText("Not evaluated. Generate a candidate to check feasibility. No CFD is executed.")
        for curve in self.curves.values():
            curve.setData([],[])

    def get_parameters(self) -> list[OptimizationParameter]:
        result = []
        for row in self.rows:
            p = deepcopy(row["parameter"])
            p.enabled = row["enabled"].isChecked()
            p.parameter_type = ParameterType(row["type"].currentData())
            p.value_mode = ValueMode(row["mode"].currentData())
            for key in ("lower","initial","upper","scale"):
                spin = row[key]
                original = getattr(p,key)
                # Preserve precise captured values unless the displayed value was edited.
                if spin.value() != round(original,spin.decimals()):
                    setattr(p,key,spin.value())
            text = row["choices"].text().strip()
            try:
                p.choices = tuple(float(v.strip()) for v in text.split(",")) if text else ()
            except ValueError as exc:
                raise ValueError(f"{p.name}: invalid numeric discrete choices.") from exc
            result.append(p)
        return result

    def get_constraints(self) -> GeometryConstraints:
        constraints = GeometryConstraints(no_self_intersection=self.no_intersection.isChecked())
        for name,(use,spin) in self.constraint_controls.items():
            setattr(constraints,name,spin.value() if use.isChecked() else None)
        return constraints

    def preview_candidate(self) -> None:
        self.apply_button.setEnabled(False)
        self.last_result = None
        for curve in self.curves.values():
            curve.setData([],[])
        try:
            mapper = ParameterMapper(self.get_parameters(),self._baseline,OptimizationMode(self.mode.currentData()))
            result = evaluate_candidate(mapper,mapper.initial_vector(),self.get_constraints())
            self.last_result = result
            header = "FEASIBLE — candidate can be applied." if result.feasible else "REJECTED — do not pass this candidate to CFD."
            lines = [header,f"Active vector dimensions: {len(mapper.active_parameters)}"]
            for check in result.feasibility.checks:
                lines.append(f"{'PASS' if check.passed else 'FAIL'} | {check.name} | actual={check.actual} | limit={check.limit} {check.message}")
            if result.geometry is not None:
                for name,curve in self.curves.items():
                    s = getattr(result.geometry.master_surfaces,name.lower())
                    curve.setData(s.x,s.y)
                lines.extend("Geometry note: "+issue.message for issue in result.geometry.warnings)
                t = result.geometry.metrics.throat
                if t is not None:
                    lines.append(f"Throat location: {t.blade1_segment} / adjacent {t.blade2_segment} (edge location is allowed)")
                self.plot.disableAutoRange()
            self.report.setPlainText("\n".join(lines))
            self.apply_button.setEnabled(result.feasible)
        except (ValueError,ArithmeticError) as exc:
            self.report.setPlainText(f"Configuration error: {exc}")

    def apply_candidate(self) -> None:
        if self.last_result is not None and self.last_result.feasible:
            self.applyRequested.emit(deepcopy(self.last_result.design))
