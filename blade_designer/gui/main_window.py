from pathlib import Path
from copy import deepcopy
import numpy as np
from PySide6.QtCore import QTimer, Qt, QEvent
from PySide6.QtGui import QAction, QUndoStack
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QAbstractSpinBox, QLineEdit, QRadioButton, QCheckBox, QSplitter, QSizePolicy, QComboBox, QLabel, QTabWidget, QScrollArea, QPushButton, QFileDialog, QMessageBox, QPlainTextEdit)
from ..models.parameters import BladeParameters, RotationDirection
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
    def __init__(self, mode="design") -> None:
        if mode not in ("design", "optimization"):
            raise ValueError("Unknown application mode")
        super().__init__()
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
        root = QWidget()
        outer = QVBoxLayout(root)
        title = QLabel("Centrifugal Compressor Blade Designer" + (" • Optimization Mode" if mode=="optimization" else ""))
        title.setStyleSheet("font-size: 22px; font-weight: 600; padding: 6px;")
        outer.addWidget(title)
        outer.addWidget(QLabel("Impeller / Vaned Diffuser v0.3  •  βm = 0°: meridional direction  •  Normalized Meridional"))
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(self.vertical_splitter,1)
        body_widget = QWidget()
        body = QHBoxLayout(body_widget)
        body.setContentsMargins(0,0,0,0)
        self.vertical_splitter.addWidget(body_widget)
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
        self.output_editor = ImpellerOutputEditor(BladeParameters())
        edge_page = QWidget();edge_layout = QVBoxLayout(edge_page)
        self.edge_scope_label=QLabel("Impeller LE/TE Shape • Shared Across All Sections")
        edge_layout.addWidget(self.edge_scope_label)
        for name in ("Leading Edge","Trailing Edge"):
            edge_layout.addWidget(self.panel.groups[name])
        edge_layout.addStretch()
        output_page = QWidget();output_layout = QVBoxLayout(output_page)
        output_layout.addWidget(self.panel.groups["Geometry"])
        output_layout.addWidget(self.panel.mapping.parentWidget())
        output_layout.addWidget(self.panel.groups["Output Points"])
        output_layout.addWidget(self.panel.export_settings)
        output_layout.addWidget(self.output_editor)
        output_layout.addStretch()
        for label,widget in (("Blade Angle",self.angle_editor),("Thickness",self.thickness_editor),
                ("LE / TE",edge_page),("Meridional",self.meridional_editor),("Output",output_page),
                ("Full Annulus",self.annulus_plot),
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
        body.addWidget(self.blade_plot,3)
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        self.section_selector = SectionSelector()
        self.section_selector.set_sections(self._sections)
        self.editor_target_label=QLabel("Editing: Impeller • Hub")
        editor_layout.addWidget(self.editor_target_label)
        editor_layout.addWidget(self.section_selector)
        editor_layout.addWidget(self.tabs,1)
        body.addWidget(editor,2)
        self.section_selector.selected.connect(self.select_section)
        self.section_selector.copyRequested.connect(self.copy_section)
        self.section_selector.addRequested.connect(self.add_span_section)
        self.section_selector.deleteRequested.connect(self.delete_span_section)
        self.context_tabs = QTabWidget()
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
        self.context_tabs.setMinimumHeight(320)
        self.vertical_splitter.addWidget(self.context_tabs)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.vertical_splitter.setSizes([500,320])
        toolbar = self.addToolBar("Project")
        rotation_widget=QWidget();rotation_layout=QHBoxLayout(rotation_widget);rotation_layout.setContentsMargins(4,0,4,0)
        rotation_layout.addWidget(QLabel("Rotation Direction • Viewed from +Z axis"))
        self.rotation_ccw=QRadioButton("CCW");self.rotation_cw=QRadioButton("CW");self.rotation_ccw.setChecked(True)
        for button in (self.rotation_ccw,self.rotation_cw):
            rotation_layout.addWidget(button);button.toggled.connect(self._rotation_changed)
        toolbar.addWidget(rotation_widget)
        toolbar.addAction("Reverse Rotation").triggered.connect(self.reverse_rotation)
        edit_menu=self.menuBar().addMenu("Edit")
        self.undo_action=QAction("Undo",self);self.undo_action.setShortcut("Ctrl+Z");self.undo_action.triggered.connect(self.undo)
        self.redo_action=QAction("Redo",self);self.redo_action.setShortcuts(["Ctrl+Y","Ctrl+Shift+Z"]);self.redo_action.triggered.connect(self.redo)
        for action in (self.undo_action,self.redo_action):edit_menu.addAction(action);toolbar.addAction(action)
        self.undo_stack.canRedoChanged.connect(self.redo_action.setEnabled)
        self.redo_action.setEnabled(False)
        self.view_mode = QComboBox()
        self.view_mode.addItems(["Impeller", "Diffuser"])
        self.view_mode.setToolTip("Select geometry and distribution editing target")
        toolbar.addWidget(self.view_mode)
        self.view_mode.currentIndexChanged.connect(self._target_changed)
        self.projection=QComboBox();self.projection.addItems(["XY","XZ","YZ"])
        self.projection.setToolTip("Impeller projection plane");toolbar.addWidget(QLabel("Projection:"));toolbar.addWidget(self.projection)
        self.projection.currentIndexChanged.connect(self._projection_changed)
        for label,callback in (("New",self.new_project),("Open",self.open_project_dialog),("Save",self.save_project_dialog),
                ("Fit View",self.fit_view),("Diffuser Segments CSV",self.export_segments_dialog),("Diffuser Contour CSV",self.export_contour_dialog),("TurboGrid Export",self.export_turbogrid_dialog)):
            toolbar.addAction(label).triggered.connect(callback)
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setMaximumHeight(72)
        outer.addWidget(self.messages)
        self.setCentralWidget(root)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.update_geometry)
        self.output_editor.parametersChanged.connect(self._output_changed)
        self.meridional_editor.stationsChanged.connect(self._stations_changed)
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
        self.update_geometry()
        self.fit_view()
        self._reset_history()
        if mode=="optimization":
            self.view_mode.setCurrentIndex(1)
            self.capture_optimization_baseline()
            self.tabs.setCurrentIndex(self.tabs.count()-1)

    def open_optimization_mode(self):
        window=MainWindow(mode="optimization")
        window.set_parameters(deepcopy(self.get_parameters()))
        window.update_geometry();window.capture_optimization_baseline();window._reset_history();window.fit_view()
        self._optimization_windows.append(window)
        window.show()
        return window

    def fit_view(self) -> None:
        self.meridional_editor.fit_view()
        self.preview_3d.fit_view()
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
        curvature_index=self.tabs.indexOf(self.curvature_plot)
        self.tabs.setTabVisible(curvature_index,self._editing_target==1)
        self.output_editor.setVisible(self._editing_target==0)
        self.section_selector.setVisible(self._editing_target==0)
        self.projection.setEnabled(self._editing_target==0)
        self.projection.blockSignals(True)
        self.projection.setCurrentText(self._impeller_projection if self._editing_target==0 else "XY")
        self.projection.blockSignals(False)
        name="Hub" if section.span==0 else "Tip" if section.span==1 else f"Span {section.span:.6g}"
        self.editor_target_label.setText("Editing: Impeller • Hub + Tip / All Span Profiles" if self._editing_target==0 else "Editing: Diffuser")
        self._bind_history_inputs()

    def _projection_changed(self):
        if self._editing_target==0:self._impeller_projection=self.projection.currentText()
        else:
            self.projection.blockSignals(True);self.projection.setCurrentText("XY");self.projection.blockSignals(False)
        self.update_geometry()

    def _target_changed(self,index):
        if not hasattr(self,"timer"):return
        self.commit_edit()
        previous=self._restoring;self._restoring=True
        try:
            self._store_section()
            self._editing_target=index
            self._load_active_profile()
            self.update_geometry()
        finally:self._restoring=previous
        self._committed_target=index

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
        self.context_meridional.update_geometry(impeller,params.flow_path,params.resolution.mean_points)
        self.context_meridional.update_blade_edges(impeller,params)
        self.meridional_editor.context.update_geometry(impeller,params.flow_path,params.resolution.mean_points)
        self.meridional_editor.context.update_blade_edges(impeller,params)
        self.blade_plot.update_geometry(geometry,params.geometry.vane_count)
        selected = impeller.sections[self._section_index]
        section_name = "Hub" if selected.span==0 else "Tip" if selected.span==1 else f"Span {selected.span:.6g}"
        plane=self.projection.currentText()
        self.blade_plot.setTitle(f"Impeller • {section_name} • {plane} projection" if self._editing_target==0 else "Vaned Diffuser • XY")
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
        self.set_parameters(BladeParameters())
        if self.optimization_widget is not None:self.optimization_widget.set_baseline(BladeParameters())
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
