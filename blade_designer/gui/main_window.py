from pathlib import Path
from copy import deepcopy
import numpy as np
from PySide6.QtCore import QTimer, Qt, QEvent
from PySide6.QtGui import QAction, QUndoStack
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QApplication, QAbstractSpinBox, QLineEdit, QRadioButton, QCheckBox, QSplitter, QSizePolicy, QComboBox, QLabel, QTabWidget, QScrollArea, QPushButton, QFileDialog, QMessageBox, QPlainTextEdit, QStackedWidget, QDialog, QToolButton, QMenu)
from ..models.parameters import BladeParameters, BladeRow, RotationDirection
from ..models.blade_rows import initial_rows, row_snapshot, row_parameters
from .design_navigator import DesignNavigator
from .undo_commands import ProjectEditCommand
from ..models.geometry import BladeGeometry
from ..models.validation import validate_parameters, ValidationLevel
from ..geometry.designer import BladeDesigner,diffuser_design_parameters
from ..fileio.project_io import save_project, load_project
from ..fileio.turbogrid_export import export_turbogrid
from ..fileio.csv_export import export_segments_csv, export_contour_csv
from .parameter_panel import ParameterPanel
from .meridional_editor import MeridionalEditor
from .section_selector import SectionSelector
from .preview_3d import Preview3D
from ..geometry.flow_area import calculate_flow_area
from .flow_area_widget import FlowAreaWidget
from .context_meridional import ContextMeridional
from .output_editor import ImpellerOutputEditor
from .profile_distribution_editor import ProfileDistributionEditor
from .plot_widgets import BladePlotWidget, FullAnnulusPlotWidget, CurvaturePlotWidget
from .metrics_widget import MetricsWidget
from .optimization_widget import OptimizationWidget


class MainWindow(QMainWindow):
    def __init__(self, mode="design", default_parameters=None) -> None:
        if mode not in ("design", "optimization"):
            raise ValueError("Unknown application mode")
        super().__init__()
        self._default_parameters = deepcopy(default_parameters if default_parameters is not None else BladeParameters())
        self.mode = mode
        self._optimization_windows = []
        self.setWindowTitle("Centrifugal Compressor Blade Designer — Impeller / Vaned Diffuser v0.3")
        if mode == "optimization":self.setWindowTitle("Blade Designer — Optimization Mode v0.3")
        self.resize(1440,1000)
        self.undo_stack = QUndoStack(self);self.undo_stack.setUndoLimit(200)
        self._restoring = False;self._dragging = False;self._committed = None
        self.designer = BladeDesigner()
        self.geometry: BladeGeometry | None = None
        self.impeller_geometry = None
        self.project_path: Path | None = None
        self._sections = deepcopy(BladeParameters().sections)
        self._section_index = 0
        self._editing_target = 0
        self._impeller_projection = "XY"
        self._diffuser_profile = deepcopy(BladeParameters().diffuser_profile)
        self._blade_rows = None
        self._active_row = None
        self._row_seed = BladeParameters()
        self._editing_meridional = False
        self._tool_dialogs = {}
        root = QWidget()
        outer = QVBoxLayout(root)
        title = QLabel("Centrifugal Compressor Blade Designer" + (" • Optimization Mode" if mode=="optimization" else ""))
        title.setStyleSheet("font-size: 22px; font-weight: 600; padding: 6px;")
        title.setWordWrap(True)
        outer.addWidget(title)
        subtitle = QLabel("Impeller / Vaned Diffuser v0.3  •  βm = 0°: meridional direction  •  Normalized Meridional")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)
        content = QHBoxLayout()
        outer.addLayout(content, 1)
        self.navigator = DesignNavigator()
        content.addWidget(self.navigator)
        self.vertical_splitter = QSplitter(Qt.Orientation.Horizontal)
        content.addWidget(self.vertical_splitter, 1)
        self.panel = ParameterPanel()
        self.tabs = QTabWidget()
        self.blade_plot = BladePlotWidget()
        self.annulus_plot = FullAnnulusPlotWidget()
        self.angle_editor = ProfileDistributionEditor("blade_angle")
        self.thickness_editor = ProfileDistributionEditor("thickness")
        self.curvature_plot = CurvaturePlotWidget()
        self.metrics_widget = MetricsWidget()
        self.optimization_widget = OptimizationWidget() if mode == "optimization" else None
        self.meridional_editor = MeridionalEditor()
        self.preview_3d = Preview3D()
        self.model_preview_3d = Preview3D()
        self.model_preview_3d.setMinimumSize(160, 180)
        self.model_preview_3d.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.output_editor = ImpellerOutputEditor(BladeParameters())
        edge_page = QWidget();edge_layout = QVBoxLayout(edge_page)
        self.edge_scope_label=QLabel("Impeller LE/TE Shape • Shared Across All Sections")
        edge_layout.addWidget(self.edge_scope_label)
        for name in ("Leading Edge","Trailing Edge"):
            edge_layout.addWidget(self.panel.groups[name])
        edge_layout.addStretch()
        output_page = QWidget();output_layout = QVBoxLayout(output_page)
        self.output_page = output_page
        output_layout.addWidget(self.panel.groups["Geometry"])
        output_layout.addWidget(self.panel.mapping.parentWidget())
        output_layout.addWidget(self.panel.groups["Output Points"])
        output_layout.addWidget(self.panel.export_settings)
        output_layout.addWidget(self.output_editor)
        output_layout.addStretch()
        annulus_page = QWidget();annulus_layout = QVBoxLayout(annulus_page)
        self.annulus_2d = QCheckBox("2D Full Annulus")
        self.annulus_3d = QCheckBox("3D Full Annulus")
        annulus_layout.addWidget(self.annulus_2d);annulus_layout.addWidget(self.annulus_3d);annulus_layout.addStretch()
        for label,widget in (("Blade Angle",self.angle_editor),("Thickness",self.thickness_editor),
                ("LE / TE",edge_page),("Meridional",self.meridional_editor),("Output",output_page),
                ("Full Annulus",annulus_page),
                ("Diffuser Curvature",self.curvature_plot)):
            if widget in (edge_page,output_page,self.panel,self.meridional_editor,self.optimization_widget):
                scroll = QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(widget)
                self.tabs.addTab(scroll,label)
            else:self.tabs.addTab(widget,label)
        if self.optimization_widget is not None:
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(self.optimization_widget)
            self.tabs.addTab(scroll,"Optimization")
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Expanding)
        self.central_views = QStackedWidget()
        self.central_views.setMinimumSize(160, 0)
        self.central_views.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        for distribution in (self.angle_editor, self.thickness_editor):
            distribution.scroll.setMinimumHeight(0)
            distribution.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.meridional_editor.context.region_legend.hide()
        self.meridional_editor.context.legend.hide()
        self.meridional_editor.context.setMinimumHeight(240)
        for widget in (self.blade_plot, self.annulus_plot):
            widget.setMinimumSize(0, 0)
            self.central_views.addWidget(widget)
        self.model_splitter = QSplitter(Qt.Orientation.Vertical)
        self.model_splitter.setChildrenCollapsible(False)
        self.model_splitter.addWidget(self.central_views)
        self.model_splitter.addWidget(self.model_preview_3d)
        self.model_splitter.setStretchFactor(0, 3)
        self.model_splitter.setStretchFactor(1, 2)
        self.model_splitter.setSizes([450, 300])
        self.vertical_splitter.addWidget(self.model_splitter)
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor.setMinimumSize(160, 0)
        editor.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.section_selector = SectionSelector()
        self.section_selector.set_sections(self._sections)
        self.editor_target_label=QLabel("Editing: Impeller • Hub")
        self.editor_target_label.setWordWrap(True)
        editor_layout.addWidget(self.editor_target_label)
        self.blade_count_widget = QWidget()
        count_layout = QHBoxLayout(self.blade_count_widget)
        count_layout.setContentsMargins(0,0,0,0)
        self.blade_count = self.panel.controls["vane_count"]
        old_row = self.panel.groups["Geometry"].layout().takeRow(self.blade_count)
        old_row.labelItem.widget().deleteLater()
        count_layout.addWidget(QLabel("翼枚数 / Blade Count"))
        count_layout.addWidget(self.blade_count)
        editor_layout.addWidget(self.blade_count_widget)
        editor_layout.addWidget(self.section_selector)
        editor_layout.addWidget(self.tabs,1)
        self.vertical_splitter.addWidget(editor)
        self.vertical_splitter.setStretchFactor(0, 3)
        self.vertical_splitter.setStretchFactor(1, 2)
        self.vertical_splitter.setSizes([660, 440])
        self.section_selector.selected.connect(self.select_section)
        self.section_selector.addRequested.connect(self.add_span_section)
        self.section_selector.deleteRequested.connect(self.delete_span_section)
        # Retain analysis widgets and their programmatic API, without a bottom panel.
        self.context_tabs = QTabWidget(root)
        self.context_meridional = ContextMeridional()
        self.flow_area_widget = FlowAreaWidget()
        for label,widget in (("Meridional",self.context_meridional),
                             ("Flow Area",self.flow_area_widget),
                             ("Metrics",self.metrics_widget),("3D Preview",self.preview_3d)):
            self.context_tabs.addTab(widget,label)
        self.flow_area_widget.stationChosen.connect(self.context_meridional.show_crossflow)
        self.flow_area_widget.stationChosen.connect(self.meridional_editor.context.show_crossflow)
        self.context_meridional.stationSelected.connect(lambda value:self.flow_area_widget.select_position(value,exact=True))
        self.meridional_editor.context.stationSelected.connect(lambda value:self.flow_area_widget.select_position(value,exact=True))
        self.meridional_editor.station_table.cellClicked.connect(lambda row,column:self.flow_area_widget.select_position(self.meridional_editor.flow_path.stations[row].m_flow_norm,exact=True))
        self.context_tabs.hide()
        self.vertical_splitter.setChildrenCollapsible(False)
        toolbar = self.addToolBar("Project")
        toolbar.setMovable(False)
        self.toolbar_groups = {}
        def group(name):
            button = QToolButton()
            button.setText(name)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu = QMenu(button)
            button.setMenu(menu)
            toolbar.addWidget(button)
            self.toolbar_groups[name] = button
            return menu
        project_menu = group("Project")
        for label, callback in (("New", self.new_project), ("Open", self.open_project_dialog), ("Save", self.save_project_dialog)):
            project_menu.addAction(label).triggered.connect(callback)
        edit_toolbar_menu = group("Edit")
        view_toolbar_menu = group("View")
        for label,box in (("2D Full Annulus",self.annulus_2d),("3D Full Annulus",self.annulus_3d)):
            action=QAction(label,self);action.setCheckable(True)
            action.toggled.connect(box.setChecked);box.toggled.connect(action.setChecked)
            view_toolbar_menu.addAction(action)
        view_toolbar_menu.addAction("Fit View").triggered.connect(self.fit_view)
        view_toolbar_menu.addAction("Output Settings").triggered.connect(self.show_output_settings)
        for label in ("Flow Area", "Metrics", "3D Preview", "Diffuser Curvature"):
            view_toolbar_menu.addAction(label).triggered.connect(lambda checked=False, name=label: self.show_analysis_view(name))
        toolbar.addSeparator()
        rotation_widget=QWidget();rotation_layout=QHBoxLayout(rotation_widget);rotation_layout.setContentsMargins(4,0,4,0)
        rotation_layout.addWidget(QLabel("Rotation (+Z)"))
        rotation_widget.setToolTip("Rotation Direction • Viewed from +Z axis")
        self.rotation_ccw=QRadioButton("CCW");self.rotation_cw=QRadioButton("CW");self.rotation_ccw.setChecked(True)
        for button in (self.rotation_ccw,self.rotation_cw):
            rotation_layout.addWidget(button);button.toggled.connect(self._rotation_changed)
        toolbar.addWidget(rotation_widget)
        toolbar.addAction("Reverse").triggered.connect(self.reverse_rotation)
        edit_menu=self.menuBar().addMenu("Edit")
        self.undo_action=QAction("Undo",self);self.undo_action.setShortcut("Ctrl+Z");self.undo_action.triggered.connect(self.undo)
        self.redo_action=QAction("Redo",self);self.redo_action.setShortcuts(["Ctrl+Y","Ctrl+Shift+Z"]);self.redo_action.triggered.connect(self.redo)
        for action in (self.undo_action,self.redo_action):edit_menu.addAction(action);edit_toolbar_menu.addAction(action)
        self.undo_stack.canRedoChanged.connect(self.redo_action.setEnabled)
        self.redo_action.setEnabled(False)
        self.view_mode = QComboBox()
        self.view_mode.addItems(["Impeller", "Diffuser"])
        self.view_mode.setToolTip("Select geometry and distribution editing target")
        self.view_mode.setParent(root)
        self.view_mode.hide()
        self.view_mode.currentIndexChanged.connect(self._target_changed)
        self.projection=QComboBox();self.projection.addItems(["XY","XZ","YZ"])
        self.projection.setToolTip("Impeller projection plane");toolbar.addWidget(QLabel("Projection:"));toolbar.addWidget(self.projection)
        self.projection.currentIndexChanged.connect(self._projection_changed)
        toolbar.addSeparator()
        export_menu = group("Export")
        for label,callback in (("Diffuser Segments CSV",self.export_segments_dialog),("Diffuser Contour CSV",self.export_contour_dialog),("TurboGrid Export",self.export_turbogrid_dialog)):
            export_menu.addAction(label).triggered.connect(callback)
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setFixedHeight(48)
        outer.addWidget(self.messages)
        self.setCentralWidget(root)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.update_geometry)
        self.output_editor.parametersChanged.connect(self._output_changed)
        self.meridional_editor.stationsChanged.connect(self._stations_changed)
        self.meridional_editor.ownershipChanged.connect(self._ensure_blade_rows)
        self.meridional_editor.parametersChanged.connect(self._schedule_update)
        self.panel.parametersChanged.connect(self._schedule_update)
        self.angle_editor.pointsChanged.connect(self._schedule_update)
        self.thickness_editor.pointsChanged.connect(self._schedule_update)
        self.panel.editAngleRequested.connect(lambda: self._open_diffuser_editor(self.angle_editor))
        self.panel.editThicknessRequested.connect(lambda: self._open_diffuser_editor(self.thickness_editor))
        if self.optimization_widget is not None:
            self.optimization_widget.captureRequested.connect(self.capture_optimization_baseline)
            self.optimization_widget.applyRequested.connect(self.apply_optimization_candidate)
        self._load_active_profile()
        self.navigator.meridionalSelected.connect(self._select_meridional)
        self.navigator.rowSelected.connect(self.select_blade_row)
        self.navigator.addRequested.connect(self.add_blade_row)
        self.navigator.deleteRequested.connect(self.delete_blade_row)
        self.navigator.moveRequested.connect(self.move_blade_row)
        self._refresh_navigator()
        self.tabs.currentChanged.connect(self._editor_tab_changed)
        self.tabs.tabBarClicked.connect(self._editor_tab_changed)
        self.annulus_2d.toggled.connect(self._refresh_model_view)
        self.annulus_3d.toggled.connect(self._refresh_model_view)
        self._configure_editor_tabs()
        self.central_views.setCurrentWidget(self.blade_plot)
        mode_menu=self.menuBar().addMenu("Mode")
        mode_menu.addAction("Open Optimization Mode in Separate Window").triggered.connect(self.open_optimization_mode)
        file_menu = self.menuBar().addMenu("File")
        for label,shortcut,callback in (
                ("New","Ctrl+N",self.new_project),("Open Project","Ctrl+O",self.open_project_dialog),
                ("Save Project","Ctrl+S",self.save_project_dialog),
                ("Export Segments CSV","",self.export_segments_dialog),
                ("Export Closed Contour CSV","",self.export_contour_dialog),("Exit","",self.close)):
            action = QAction(label,self)
            if shortcut: action.setShortcut(shortcut)
            action.triggered.connect(callback)
            file_menu.addAction(action)
        for editor in (self.angle_editor,self.thickness_editor):
            editor.dragStarted.connect(self._begin_drag);editor.dragFinished.connect(self._end_drag)
            editor.editFinished.connect(self.commit_edit)
        self.meridional_editor.editFinished.connect(self.commit_edit)
        for context in (self.context_meridional,self.meridional_editor.context):
            context.endpointMoved.connect(self.meridional_editor.blade_edges.move_endpoint)
            context.edgeDragStarted.connect(self._begin_drag);context.edgeDragFinished.connect(self._end_drag)
        self._bind_history_inputs()
        if default_parameters is not None:
            self.set_parameters(self._default_parameters)
        self.update_geometry()
        self.fit_view()
        self._reset_history()
        if mode=="optimization":
            self.view_mode.setCurrentIndex(1)
            self.capture_optimization_baseline()
            self.tabs.setCurrentIndex(self.tabs.count()-1)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1440, available.width() - 40), min(900, available.height() - 80))

    def _configure_editor_tabs(self):
        allowed = {"Meridional"} if self._editing_meridional else {"Blade Angle", "Thickness", "LE / TE", "Full Annulus"}
        if self.mode == "optimization" and not self._editing_meridional:
            allowed.add("Optimization")
        self.tabs.blockSignals(True)
        try:
            for index in range(self.tabs.count()):
                self.tabs.setTabVisible(index, self.tabs.tabText(index) in allowed)
            current = self.tabs.currentIndex()
            if current < 0 or not self.tabs.isTabVisible(current):
                self.tabs.setCurrentIndex(next(index for index in range(self.tabs.count()) if self.tabs.isTabVisible(index)))
        finally:
            self.tabs.blockSignals(False)
        self.section_selector.setVisible(not self._editing_meridional and self._editing_target == 0)
        self.blade_count_widget.setVisible(not self._editing_meridional)

    def _editor_tab_changed(self, index):
        self._refresh_model_view()

    def _refresh_model_view(self, *args):
        self.central_views.setCurrentWidget(self.annulus_plot if self.annulus_2d.isChecked() else self.blade_plot)
        count = self.panel.controls["vane_count"].value()
        self.model_preview_3d.set_full_annulus(self.annulus_3d.isChecked(), count)

    def _show_tool_dialog(self, name, widget):
        if name not in self._tool_dialogs:
            dialog = QDialog(self)
            dialog.setWindowTitle(name)
            layout = QVBoxLayout(dialog)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            layout.addWidget(scroll)
            screen = self.screen().availableGeometry()
            dialog.resize(min(850, screen.width() - 40), min(650, screen.height() - 80))
            self._tool_dialogs[name] = dialog
        dialog = self._tool_dialogs[name]
        dialog.show()
        dialog.raise_()
        return dialog

    def show_output_settings(self):
        return self._show_tool_dialog("Output Settings", self.output_page)

    def show_analysis_view(self, name):
        widget = {"Flow Area": self.flow_area_widget, "Metrics": self.metrics_widget,
                  "3D Preview": self.preview_3d, "Diffuser Curvature": self.curvature_plot}[name]
        return self._show_tool_dialog(name, widget)

    def open_optimization_mode(self):
        window=MainWindow(mode="optimization", default_parameters=self._default_parameters)
        window.set_parameters(deepcopy(self.get_parameters()))
        if window._blade_rows is not None:
            active = next(row for row in window._blade_rows if row.identifier == window._active_row)
            diffuser = active if active.kind == "diffuser" else next((row for row in window._blade_rows if row.kind == "diffuser"), None)
            if diffuser is None:
                window.add_blade_row("diffuser")
            else:
                window.select_blade_row(diffuser.identifier)
        window.update_geometry();window.capture_optimization_baseline();window._reset_history();window.fit_view()
        window.tabs.setCurrentIndex(window.tabs.count() - 1)
        self._optimization_windows.append(window)
        window.show()
        return window

    def fit_view(self) -> None:
        self.meridional_editor.fit_view()
        self.preview_3d.fit_view()
        self.model_preview_3d.fit_view()
        self.context_meridional.fit_view()
        self.flow_area_widget.fit_view()
        for plot in (self.blade_plot,self.annulus_plot,self.angle_editor.plot,self.thickness_editor.plot,
                     self.curvature_plot.plot,self.metrics_widget.plot,
                     *([self.optimization_widget.plot] if self.optimization_widget is not None else [])):
            plot.autoRange()
            plot.disableAutoRange()

    def get_parameters(self) -> BladeParameters:
        p = self.panel.get_parameters()
        p.rotation_direction=RotationDirection.CCW if self.rotation_ccw.isChecked() else RotationDirection.CW
        self.meridional_editor.blade_edges.apply_to(p)
        self.output_editor.apply_to(p)
        p.hub,p.shroud = self.meridional_editor.get_curves()
        p.flow_path = self.meridional_editor.get_stations()
        self._store_section(p)
        p.sections = deepcopy(self._sections)
        p.diffuser_profile=deepcopy(self._diffuser_profile)
        hub = p.sections[0]
        p.blade_angle,p.thickness,p.edges = hub.blade_angle,hub.thickness,hub.edge_parameters
        if self._blade_rows is not None:
            active = next(row for row in self._blade_rows if row.identifier == self._active_row)
            active.parameters = row_snapshot(p)
            p.blade_rows = deepcopy(self._blade_rows)
            p.active_blade_row = self._active_row
        else:
            p.blade_rows = None
            p.active_blade_row = None
        return p

    @staticmethod
    def _with_shared_impeller_edges(params):
        params=deepcopy(params)
        common=params.sections[0].edge_parameters
        for section in params.sections:
            section.edge_parameters=deepcopy(common)
        return params

    def set_parameters(self, params: BladeParameters) -> None:
        params=self._with_shared_impeller_edges(params)
        previous=self._restoring;self._restoring=True
        try:self._set_parameters(params)
        finally:self._restoring=previous
        self._bind_history_inputs()

    def _set_parameters(self, params):
        if params.blade_rows is None:
            self._row_seed = row_snapshot(params)
        self._blade_rows = deepcopy(params.blade_rows)
        self._active_row = params.active_blade_row
        if self._blade_rows is not None:
            row = next(row for row in self._blade_rows if row.identifier == self._active_row)
            self._editing_target = 0 if row.kind == "impeller" else 1
            self.view_mode.blockSignals(True)
            self.view_mode.setCurrentIndex(self._editing_target)
            self.view_mode.blockSignals(False)
        self.meridional_editor.blade_edges.set_parameters(params)
        (self.rotation_ccw if params.rotation_direction==RotationDirection.CCW else self.rotation_cw).setChecked(True)
        self.output_editor.set_parameters(params)
        self.meridional_editor.mean_points=params.resolution.mean_points
        self.meridional_editor.set_curves(params.hub,params.shroud)
        self.meridional_editor.set_stations(params.flow_path)
        self.panel.set_parameters(params)
        self._sections = deepcopy(params.sections)
        self._diffuser_profile = deepcopy(params.diffuser_profile)
        self._section_index = 0
        self.section_selector.set_sections(self._sections)
        self._load_active_profile()
        self._refresh_navigator()

    def _store_section(self,p=None):
        p = self.panel.get_parameters() if p is None else p
        profiles = self._sections if self._editing_target==0 else [self._diffuser_profile]
        for profile in profiles:
            profile.blade_angle.points = self.angle_editor.series[profile.span].get_points()
            profile.thickness.points = self.thickness_editor.series[profile.span].get_points()
            profile.edge_parameters = deepcopy(p.edges)

    def select_section(self,index):
        if index < 0:return
        self.commit_edit()
        previous=self._restoring;self._restoring=True
        try:self._select_section(index)
        finally:self._restoring=previous
        self._committed_span=self._sections[index].span

    def _active_profile(self):
        return self._sections[self._section_index] if self._editing_target==0 else self._diffuser_profile

    def _load_active_profile(self):
        section=self._active_profile()
        p=self.panel.get_parameters();p.edges=deepcopy(self._sections[0].edge_parameters if self._editing_target==0 else section.edge_parameters)
        self.panel.set_parameters(p)
        profiles=self._sections if self._editing_target==0 else [self._diffuser_profile]
        for editor,attribute in ((self.angle_editor,"blade_angle"),(self.thickness_editor,"thickness")):
            editor.set_profiles([(profile.span,
                ("Hub" if profile.span==0 else "Tip" if profile.span==1 else f"Span {profile.span:.6g}") if self._editing_target==0 else "Diffuser",
                getattr(profile,attribute).points) for profile in profiles],section.span)
        form=self.panel.groups["Geometry"].layout()
        for name in ("r_le","r_te"):
            form.setRowVisible(self.panel.controls[name],self._editing_target==1)
        self.panel.groups["Geometry"].setTitle("Diffuser Dimensions / Blade Count" if self._editing_target else "Blade Placement / Blade Count")
        self.section_selector.combo.setToolTip("Select blade view and Full Annulus section. Impeller LE/TE shape is common to all sections.")
        self.edge_scope_label.setText("Impeller LE/TE Shape • Shared Across All Sections" if self._editing_target==0 else "Diffuser LE/TE Shape")
        self.output_editor.setVisible(self._editing_target==0)
        self.section_selector.setVisible(self._editing_target==0)
        self.projection.setEnabled(self._editing_target==0)
        self.projection.blockSignals(True)
        self.projection.setCurrentText(self._impeller_projection if self._editing_target==0 else "XY")
        self.projection.blockSignals(False)
        name="Hub" if section.span==0 else "Tip" if section.span==1 else f"Span {section.span:.6g}"
        self.editor_target_label.setText("Editing: Impeller • Hub + Tip / All Span Profiles" if self._editing_target==0 else "Editing: Diffuser")
        if self._blade_rows is not None:
            row = next(row for row in self._blade_rows if row.identifier == self._active_row)
            self.editor_target_label.setText(f"Editing: {row.name} • {row.kind.title()}")
        if self._editing_meridional:
            self.editor_target_label.setText("Editing: Meridional • shared Hub / Shroud")
        self._configure_editor_tabs()
        self._editor_tab_changed(self.tabs.currentIndex())
        self._bind_history_inputs()

    def _projection_changed(self):
        if self._editing_target==0:self._impeller_projection=self.projection.currentText()
        else:
            self.projection.blockSignals(True);self.projection.setCurrentText("XY");self.projection.blockSignals(False)
        self.update_geometry()

    def _target_changed(self,index):
        if not hasattr(self,"timer"):return
        self._editing_meridional = False
        if self._blade_rows is not None:
            kind = "impeller" if index == 0 else "diffuser"
            row = next((row for row in self._blade_rows if row.kind == kind), None)
            if row is not None:
                self.select_blade_row(row.identifier)
            else:
                self.view_mode.blockSignals(True)
                self.view_mode.setCurrentIndex(self._editing_target)
                self.view_mode.blockSignals(False)
            return
        self.commit_edit()
        previous=self._restoring;self._restoring=True
        try:
            self._store_section()
            self._editing_target=index
            self._load_active_profile()
            self.update_geometry()
        finally:self._restoring=previous
        self._committed_target=index
        self._refresh_navigator()

    def _select_meridional(self):
        self.commit_edit()
        self._editing_meridional = True
        self._configure_editor_tabs()
        self.editor_target_label.setText("Editing: Meridional • shared Hub / Shroud")
        self._refresh_model_view()
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == "Meridional":
                self.tabs.setCurrentIndex(index)
                break

    def _refresh_navigator(self, select_row=False):
        if not hasattr(self, "navigator"):
            return
        rows = self._blade_rows or initial_rows(self.panel.get_parameters())
        identifier = self._active_row or ("row-1" if self._editing_target == 0 else "row-2")
        self.navigator.set_rows(rows, identifier, select_row=select_row)
        self.meridional_editor.set_blade_rows(rows)

    def _ensure_blade_rows(self):
        if self._blade_rows is None:
            params = self.get_parameters()
            self._blade_rows = initial_rows(params)
            self._active_row = "row-1" if self._editing_target == 0 else "row-2"
            other = self._blade_rows[1 if self._editing_target == 0 else 0]
            for name in ("geometry", "rotation_direction", "surface_mapping", "output_points", "export", "turbogrid"):
                setattr(other.parameters, name, deepcopy(getattr(self._row_seed, name)))

    def _activate_blade_row(self, identifier):
        self._editing_meridional = False
        project = self.get_parameters()
        row = next(row for row in self._blade_rows if row.identifier == identifier)
        params = row_parameters(project, row)
        params.blade_rows = deepcopy(self._blade_rows)
        params.active_blade_row = identifier
        self.set_parameters(params)
        self.update_geometry()
        self.tabs.setCurrentWidget(self.angle_editor)
        self._refresh_model_view()
        self._refresh_navigator(select_row=True)

    def select_blade_row(self, identifier):
        self.commit_edit()
        self._editing_meridional = False
        if self._blade_rows is not None and self._active_row == identifier:
            self._load_active_profile()
            self.tabs.setCurrentWidget(self.angle_editor)
            self._refresh_model_view()
            self._refresh_navigator(select_row=True)
            return
        self._ensure_blade_rows()
        if not any(row.identifier == identifier for row in self._blade_rows):
            return
        previous = self._restoring
        self._restoring = True
        try:
            self._activate_blade_row(identifier)
        finally:
            self._restoring = previous
        # Selection alone is not an edit; the next edit starts from this row.
        self._committed = deepcopy(self.get_parameters())
        self._committed_span = self._sections[self._section_index].span
        self._committed_target = self._editing_target

    def add_blade_row(self, kind, name=None):
        if kind not in ("impeller", "diffuser"):
            raise ValueError("Unknown blade row type.")
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise ValueError("Blade row name is required.")
        self.commit_edit()
        self._ensure_blade_rows()
        params = self.get_parameters()
        source = next((row.parameters for row in self._blade_rows if row.kind == kind), params)
        number = 1
        while any(row.identifier == f"row-{number}" for row in self._blade_rows):
            number += 1
        identifier = f"row-{number}"
        self._blade_rows.append(BladeRow(identifier, name.strip() if name is not None else f"{kind.title()} {number}", kind, row_snapshot(source)))
        previous = self._restoring
        self._restoring = True
        try:
            self._activate_blade_row(identifier)
        finally:
            self._restoring = previous
        self.commit_edit()

    def delete_blade_row(self):
        self.commit_edit()
        self._ensure_blade_rows()
        if len(self._blade_rows) <= 1:
            return
        project = self.get_parameters()
        index = next(i for i, row in enumerate(self._blade_rows) if row.identifier == self._active_row)
        removed = self._blade_rows[index].identifier
        del self._blade_rows[index]
        curves = [project.hub, project.shroud]
        for remaining in self._blade_rows:
            curves.extend((remaining.parameters.hub, remaining.parameters.shroud))
        for curve in curves:
            for segment in curve.segments:
                if segment.blade_row == removed: segment.blade_row = None
        row = self._blade_rows[min(index, len(self._blade_rows) - 1)]
        params = row_parameters(project, row)
        params.blade_rows = deepcopy(self._blade_rows)
        params.active_blade_row = row.identifier
        previous = self._restoring
        self._restoring = True
        try:
            self.set_parameters(params)
            self.update_geometry()
            self._refresh_navigator(select_row=True)
        finally:
            self._restoring = previous
        self.commit_edit()

    def move_blade_row(self, direction):
        if direction not in (-1, 1):
            return
        self.commit_edit()
        self._ensure_blade_rows()
        index = next(i for i, row in enumerate(self._blade_rows) if row.identifier == self._active_row)
        destination = index + direction
        if not 0 <= destination < len(self._blade_rows):
            return
        self._blade_rows[index], self._blade_rows[destination] = self._blade_rows[destination], self._blade_rows[index]
        self._refresh_navigator()
        self.commit_edit()

    def _open_diffuser_editor(self,editor):
        self.view_mode.setCurrentIndex(1)
        self.tabs.setCurrentWidget(editor)

    def _select_section(self,index):
        self._store_section()
        self._section_index=index
        self._load_active_profile()
        self.update_geometry()

    def copy_section(self,hub_to_tip):
        self.commit_edit()
        self._store_section()
        source,target = (0,len(self._sections)-1) if hub_to_tip else (len(self._sections)-1,0)
        self._sections[target].blade_angle=deepcopy(self._sections[source].blade_angle)
        self._sections[target].thickness=deepcopy(self._sections[source].thickness)
        self._refresh_section()

    def _refresh_section(self):
        previous=self._restoring;self._restoring=True
        try:self._refresh_section_widgets()
        finally:self._restoring=previous
        self._bind_history_inputs()
        self.commit_edit()

    def _refresh_section_widgets(self):
        self.section_selector.set_sections(self._sections,self._section_index)
        self._load_active_profile()
        self.update_geometry()

    def add_span_section(self,span):
        if not 0<span<1 or any(s.span==span for s in self._sections):return
        self.commit_edit()
        self._store_section()
        section = deepcopy(self._sections[self._section_index]);section.span = span
        self._sections.append(section);self._sections.sort(key=lambda s:s.span)
        self._section_index = self._sections.index(section)
        self._refresh_section()

    def delete_span_section(self):
        if self._sections[self._section_index].span in (0,1):return
        self.commit_edit()
        del self._sections[self._section_index];self._section_index=0
        self._refresh_section()

    def _output_changed(self):
        p=self.panel.get_parameters()
        self.output_editor.apply_to(p)
        flow=self.meridional_editor.get_stations()
        from ..models.flow_path import StationType
        flow.set_position(StationType.IMP_LE,p.blade_le_fraction)
        flow.set_position(StationType.IMP_TE,p.blade_te_fraction)
        self.meridional_editor.set_stations(flow)
        self._schedule_update()

    def _stations_changed(self):
        p=self.panel.get_parameters()
        self.output_editor.apply_to(p)
        p.flow_path=self.meridional_editor.get_stations()
        self.output_editor.set_parameters(p)

    def _schedule_update(self) -> None:
        self._bind_history_inputs()
        self.statusBar().showMessage("Updating…")
        if self._dragging:
            if not self.timer.isActive():self.timer.start(50)
        else:self.timer.start(150)

    def _display_geometry(self, geometry: BladeGeometry, params: BladeParameters, impeller=None) -> None:
        impeller = self.designer.generate_3d(params) if impeller is None else impeller
        area=calculate_flow_area(impeller.hub,impeller.shroud,params.flow_path,points=params.resolution.area_points,strict=False,mean_points=params.resolution.mean_points)
        self.flow_area_result=area
        self.flow_area_widget.update_result(area,params.flow_path)
        self.impeller_geometry = impeller
        self.preview_3d.update_geometry(impeller)
        if self._editing_target == 0:
            self.model_preview_3d.update_geometry(impeller)
        else:
            self.model_preview_3d.update_diffuser(geometry, impeller)
        self.context_meridional.update_geometry(impeller,params.flow_path,params.resolution.mean_points)
        self.context_meridional.update_blade_edges(impeller,params)
        self.meridional_editor.context.update_geometry(impeller,params.flow_path,params.resolution.mean_points)
        self.meridional_editor.context.update_blade_edges(impeller,params)
        self.blade_plot.update_geometry(geometry,params.geometry.vane_count)
        selected = impeller.sections[self._section_index]
        section_name = "Hub" if selected.span==0 else "Tip" if selected.span==1 else f"Span {selected.span:.6g}"
        plane=self.projection.currentText()
        self.blade_plot.setTitle(f"Impeller • {section_name} • {plane} projection" if self._editing_target==0 else "Vaned Diffuser • XY")
        if self._blade_rows is not None:
            row = next(row for row in self._blade_rows if row.identifier == self._active_row)
            self.blade_plot.setTitle(f"{row.name} • {section_name} • {plane} projection" if self._editing_target==0 else f"{row.name} • XY")
            self.model_preview_3d.model_label = f"{row.name} • " + self.model_preview_3d.model_label
        axes=plane.lower() if self._editing_target==0 else "xy"
        self.blade_plot.setLabel("bottom",axes[0].upper()+" [mm]")
        self.blade_plot.setLabel("left",axes[1].upper()+" [mm]")
        if self._editing_target == 0:
            self.blade_plot.camber_curve.setData(getattr(selected.camber,axes[0]),getattr(selected.camber,axes[1]))
            for name,curve in self.blade_plot.curves.items():
                segment = getattr(selected,"master_"+name.lower())
                curve.setData(getattr(segment,axes[0]),getattr(segment,axes[1]))
            self.blade_plot.adjacent.setData([],[])
            self.blade_plot.throat_line.setData([],[])
        if self._editing_target==0:
            self.annulus_plot.update_impeller_annulus(selected,params.geometry.vane_count,plane)
        else:self.annulus_plot.update_annulus(geometry,params.geometry.vane_count)
        if self._editing_target==0:
            for profile in impeller.sections:
                self.angle_editor.update_profile_distribution(profile.span,profile.camber.m_blade_norm,profile.beta_m_deg)
                self.thickness_editor.update_profile_distribution(profile.span,profile.camber.m_blade_norm,profile.thickness)
        else:
            self.angle_editor.update_distribution(geometry.camber.m_norm,np.rad2deg(geometry.camber.beta_m_rad))
            self.thickness_editor.update_distribution(geometry.camber.m_norm,geometry.thickness)
        self.curvature_plot.update_geometry(geometry)
        self.metrics_widget.update_geometry(geometry,params.geometry.vane_count)
        self.geometry = geometry
        self._refresh_model_view()
        messages = [f"{i.level.value.upper()} — {i.field}: {i.message}" for i in geometry.warnings]
        if area.errors:messages.append(f"FLOW AREA — {len(area.errors)} unavailable cross-sections: {area.errors[0]}")
        self.messages.setPlainText("\n".join(messages) if messages else "Ready")
        t = geometry.metrics.throat
        throat_text = "N/A" if t is None else f"{t.width:.6f} mm"
        self.statusBar().showMessage(f"Impeller: {len(impeller.sections)} sections  |  Diffuser {'WARNING' if messages else 'Ready'}  |  Throat = {throat_text}  |  PS: {geometry.resolved_mapping.value}")

    def update_geometry(self) -> None:
        self.timer.stop()
        try:
            params = self.get_parameters()
            geometry = self.designer.generate_diffuser(params)
            self._display_geometry(geometry,params)
        except (ValueError, ArithmeticError) as exc:
            text = f"ERROR — {exc}\nShowing last valid geometry."
            self.messages.setPlainText(text)
            self.statusBar().showMessage("ERROR — correct input values; showing last valid geometry.")

    def new_project(self) -> None:
        self.set_parameters(deepcopy(self._default_parameters))
        if self.optimization_widget is not None:self.optimization_widget.set_baseline(diffuser_design_parameters(self.get_parameters()))
        self.project_path = None
        self._reset_history()
        self.update_geometry()
        self.fit_view()

    def load_from_path(self, path: str | Path) -> None:
        params = self._with_shared_impeller_edges(load_project(path))
        geometry = self.designer.generate_diffuser(params)
        impeller = self.designer.generate_3d(params)
        self.set_parameters(params)
        if self.optimization_widget is not None:self.optimization_widget.set_baseline(diffuser_design_parameters(params))
        self.project_path = Path(path)
        self._reset_history()
        self.timer.stop()
        self._display_geometry(geometry,params,impeller)
        self.fit_view()

    def save_to_path(self, path: str | Path) -> None:
        self.commit_edit()
        params = self.get_parameters()
        self.designer.generate_3d(params)
        save_project(path,params)
        self.project_path = Path(path)
        self.statusBar().showMessage(f"Saved: {path}")

    def export_to_path(self, path: str | Path, contour: bool = False) -> None:
        if self._blade_rows is not None and self._editing_target != 1:
            raise ValueError("Select a Diffuser blade row for CSV export.")
        params = self.get_parameters()
        geometry = self.designer.generate_diffuser(params)
        (export_contour_csv if contour else export_segments_csv)(path,geometry,params.export)
        self.statusBar().showMessage(f"Exported: {path}")

    def open_project_dialog(self) -> None:
        path,_ = QFileDialog.getOpenFileName(self,"Open Project","","Project JSON (*.json)")
        if path:
            try: self.load_from_path(path)
            except (OSError,ValueError) as exc: QMessageBox.warning(self,"Open Project",str(exc))

    def save_project_dialog(self) -> None:
        path,_ = QFileDialog.getSaveFileName(self,"Save Project",str(self.project_path or "blade_v03.json"),"Project JSON (*.json)")
        if path:
            try: self.save_to_path(path)
            except (OSError,ValueError) as exc: QMessageBox.warning(self,"Save Project",str(exc))

    def _export_dialog(self, contour: bool) -> None:
        path,_ = QFileDialog.getSaveFileName(self,"Export Closed Contour CSV" if contour else "Export Segments CSV",
                     "blade_contour.csv" if contour else "blade_segments.csv","CSV (*.csv)")
        if path:
            try: self.export_to_path(path,contour)
            except (OSError,ValueError) as exc: QMessageBox.warning(self,"Export CSV",str(exc))

    def export_segments_dialog(self) -> None:
        self._export_dialog(False)

    def export_contour_dialog(self) -> None:
        self._export_dialog(True)

    def capture_optimization_baseline(self) -> None:
        if self.optimization_widget is None:return
        if self._blade_rows is not None and self._editing_target != 1:
            self.optimization_widget.report.setPlainText("Select a Diffuser blade row for optimization.")
            return
        try:
            params = self.get_parameters()
            self.designer.generate_diffuser(params)
            if self.optimization_widget is not None:self.optimization_widget.set_baseline(diffuser_design_parameters(params))
        except (ValueError, ArithmeticError) as exc:
            self.optimization_widget.report.setPlainText(f"Cannot capture baseline: {exc}")

    def apply_optimization_candidate(self, candidate: BladeParameters) -> None:
        if self.optimization_widget is None:return
        self.commit_edit()
        try:
            if self._blade_rows is not None and self._editing_target != 1:
                raise ValueError("Select a Diffuser blade row for optimization.")
            params=self.get_parameters()
            params.diffuser_profile=deepcopy(candidate.sections[0])
            params.geometry=deepcopy(candidate.geometry)
            params.surface_mapping=candidate.surface_mapping
            geometry=self.designer.generate_diffuser(params)
            impeller=self.designer.generate_3d(params)
            self._restoring=True
            try:
                self.view_mode.blockSignals(True);self.view_mode.setCurrentIndex(1);self.view_mode.blockSignals(False)
                self._editing_target=1
                self.set_parameters(params)
            finally:self._restoring=False
            self.timer.stop()
            self._display_geometry(geometry,params,impeller)
            self.tabs.setCurrentIndex(0)
            self.commit_edit()
        except (ValueError,ArithmeticError) as exc:
            self.optimization_widget.report.setPlainText(f"Cannot apply candidate: {exc}")

    def export_turbogrid_dialog(self):
        if self._blade_rows is not None and self._editing_target != 0:
            QMessageBox.warning(self, "TurboGrid Export", "Select an Impeller blade row for TurboGrid export.")
            return
        directory = QFileDialog.getExistingDirectory(self,"Export TurboGrid case directory")
        if directory:
            try:
                files = export_turbogrid(directory,self.get_parameters())
                self.statusBar().showMessage(f"TurboGrid: {len(files)} files exported to {directory}")
            except (OSError,ValueError,ArithmeticError) as exc:
                QMessageBox.warning(self,"TurboGrid Export",str(exc))

    def _bind_history_inputs(self):
        if not hasattr(self,"output_editor"):return
        for root in (self.panel,self.angle_editor,self.thickness_editor,self.meridional_editor,self.output_editor,*self.panel.groups.values(),self.panel.export_settings):
            for box in root.findChildren(QAbstractSpinBox):
                if not getattr(box,"_history_bound",False):
                    box._history_bound=True;box.editingFinished.connect(self.commit_edit)
                    box.installEventFilter(self);box.lineEdit().installEventFilter(self)
            for box in root.findChildren(QLineEdit):
                if isinstance(box.parent(),QAbstractSpinBox):continue
                if not getattr(box,'_history_bound',False):
                    box._history_bound=True;box.editingFinished.connect(self.commit_edit);box.installEventFilter(self)
            for box in root.findChildren(QComboBox)+root.findChildren(QCheckBox):
                if box is self.meridional_editor.selector:continue
                if not getattr(box,"_history_bound",False):
                    box._history_bound=True
                    signal=box.currentIndexChanged if isinstance(box,QComboBox) else box.toggled
                    signal.connect(self.commit_edit)

    def _reset_history(self):
        self.undo_stack.clear()
        self._committed=deepcopy(self.get_parameters())
        self._committed_span=self._sections[self._section_index].span
        self._committed_target=self._editing_target

    def commit_edit(self,*args):
        if self._restoring or self._dragging or self._committed is None:return
        current=self.get_parameters();span=self._sections[self._section_index].span
        if current!=self._committed:
            self.undo_stack.push(ProjectEditCommand(self,self._committed,current,self._committed_span,span,before_target=self._committed_target,after_target=self._editing_target))
            self._committed=deepcopy(current);self._committed_span=span;self._committed_target=self._editing_target

    def _restore_design(self,params,span,target=None):
        self._restoring=True
        try:
            if target is not None:
                self.view_mode.blockSignals(True);self.view_mode.setCurrentIndex(target);self.view_mode.blockSignals(False)
                self._editing_target=target
            self.set_parameters(deepcopy(params))
            index=next((i for i,s in enumerate(self._sections) if s.span==span),0)
            self._select_section(index)
            self.section_selector.set_sections(self._sections,index)
            self._committed=deepcopy(params);self._committed_span=self._sections[index].span;self._committed_target=self._editing_target
            self.update_geometry()
        finally:self._restoring=False

    def _begin_drag(self):
        self.commit_edit();self._dragging=True

    def _end_drag(self):
        self._dragging=False;self.update_geometry();self.commit_edit()

    def undo(self):
        self.commit_edit();self.undo_stack.undo()

    def redo(self):
        self.commit_edit();self.undo_stack.redo()

    def _rotation_changed(self,checked):
        if checked and hasattr(self,"timer") and not self._restoring:
            self.update_geometry();self.commit_edit()

    def reverse_rotation(self):
        self.commit_edit()
        (self.rotation_cw if self.rotation_ccw.isChecked() else self.rotation_ccw).setChecked(True)

    def eventFilter(self,watched,event):
        # SpinBox text editors otherwise consume Ctrl+Z as local text Undo.
        if event.type() in (QEvent.Type.ShortcutOverride,QEvent.Type.KeyPress):
            mods=event.modifiers()
            if mods & Qt.KeyboardModifier.ControlModifier and event.key() in (Qt.Key.Key_Z,Qt.Key.Key_Y):
                if event.type()==QEvent.Type.ShortcutOverride:
                    event.accept();return True
                if isinstance(watched,QAbstractSpinBox):watched.interpretText()
                elif isinstance(watched.parent(),QAbstractSpinBox):watched.parent().interpretText()
                if event.key()==Qt.Key.Key_Y or mods & Qt.KeyboardModifier.ShiftModifier:self.redo()
                else:self.undo()
                return True
        return super().eventFilter(watched,event)
