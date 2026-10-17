from dataclasses import asdict, fields
from pathlib import Path
from enum import Enum
import json
import os
import tempfile
from ..models.parameters import (BladeParameters, GeometryParameters, BladeAngleParameters,
    ThicknessParameters, DistributionPoint, EdgeParameters, EdgeType, OutputPointParameters,
    ExportParameters, SurfaceMapping, BladeSection, TurboGridParameters, RotationDirection, SplitterParameters)
from ..models.meridional import MeridionalCurveParameters,LineSegmentParameters,ArcSegmentParameters
from ..models.resolution import GeometryResolutionParameters
from ..models.flow_path import FlowPathParameters, ComponentStation, StationType
from .blade_edge_migration import migrate_v03_blade_edges
from ..models.blade_edge import BladeEdgePosition,BladeRowEdgeParameters
from .project_migration import migrate_v01_to_v02,migrate_v02_to_v03,migrate_v03_flow_path
from ..models.validation import validate_parameters, ValidationLevel


def _check(params: BladeParameters, check_ownership=True) -> None:
    from ..models.cad import validate_cad_parameters
    validate_cad_parameters(params.cad_export)
    if params.cad_export.disk.backside is not None:
        from ..geometry.meridional_segments import generate_meridional
        generate_meridional(params.cad_export.disk.backside)
    from ..models.blade_rows import validate_rows, row_parameters
    validate_rows(params)
    if check_ownership and params.blade_rows is None and any(segment.blade_row is not None for curve in (params.hub,params.shroud) for segment in curve.segments):
        raise ValueError("Meridional ownership requires a blade row list.")
    for row in params.blade_rows or []:
        try:
            _check(row_parameters(params, row), check_ownership=False)
        except ValueError as exc:
            raise ValueError(f"{row.name}: {exc}") from exc
    errors = [i for i in validate_parameters(params) if i.level == ValidationLevel.ERROR]
    if errors:
        raise ValueError("; ".join(f"{i.field}: {i.message}" for i in errors))
    from ..geometry.geometry_3d import generate_impeller
    generate_impeller(params)
    from ..geometry.designer import BladeDesigner
    BladeDesigner().generate_diffuser(params)
    if (params.sections[0].blade_angle,params.sections[0].thickness,params.sections[0].edge_parameters)!=(params.blade_angle,params.thickness,params.edges):
        raise ValueError("Legacy diffuser fields must match the Hub section.")
    settings=params.turbogrid
    if settings.rotation_axis not in ('X','Y','Z') or settings.geometry_unit not in ('MM','CM','M'):
        raise ValueError("Unknown TurboGrid axis or unit.")
    if any(v not in ("auto","EllipseEnd","CutOffEnd","SquareEnd") for v in (settings.leading_edge_type,settings.trailing_edge_type)):
        raise ValueError("Unknown TurboGrid edge type.")


def save_project(path: str | Path, params: BladeParameters) -> None:
    _check(params)
    payload = asdict(params)
    from ..models.cad import CadExportParameters
    default_cad=asdict(CadExportParameters())
    def omit_unassigned(value):
        if isinstance(value, dict):
            if value.get("cad_export") == default_cad:value.pop("cad_export")
            if value.get("provisional") is False:value.pop("provisional")
            if value.get("front_end_m_mm",False) is None:value.pop("front_end_m_mm")
            if value.get("splitter", False) is None:
                value.pop("splitter")
            if value.get("tip_clearance", False) is None:
                value.pop("tip_clearance")
            if value.get("impeller_trim", False) is None:
                value.pop("impeller_trim")
            if value.get("impeller_te_rake_deg", False) is None:
                value.pop("impeller_te_rake_deg")
            if value.get("blade_row", False) is None:
                value.pop("blade_row")
            for child in value.values(): omit_unassigned(child)
        elif isinstance(value, list):
            for child in value: omit_unassigned(child)
    omit_unassigned(payload)
    if params.blade_rows is None:
        payload.pop("blade_rows")
        payload.pop("active_blade_row")
    def has_cad(value):
        if isinstance(value,dict):return "cad_export" in value or "tip_clearance" in value or "impeller_trim" in value or any(has_cad(v) for v in value.values())
        return isinstance(value,list) and any(has_cad(v) for v in value)
    text = json.dumps({"schema_version": "0.4" if has_cad(payload) else "0.3", **payload}, ensure_ascii=False,
                      indent=2, allow_nan=False, default=lambda value: value.value if isinstance(value, Enum) else value)
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(text + "\n")
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _group(data: dict, name: str, cls: type) -> object:
    values = data.get(name)
    if not isinstance(values, dict) or set(values) != {f.name for f in fields(cls)}:
        raise ValueError(f"Invalid or missing fields in {name}.")
    return cls(**values)


def migrate_v01(data: dict) -> BladeParameters:
    return _decode_v03(migrate_v03_blade_edges(migrate_v03_flow_path(migrate_v02_to_v03(migrate_v01_to_v02(data)))))


def _curve(values):
    if not isinstance(values,dict) or set(values)!={f.name for f in fields(MeridionalCurveParameters)}:
        raise ValueError("Invalid meridional curve fields.")
    curve=MeridionalCurveParameters(**values)
    curve.segments=[]
    for segment in values['segments']:
        if segment.get('blade_row') is not None and (not isinstance(segment['blade_row'], str) or not segment['blade_row']):
            raise ValueError("Invalid meridional blade row identifier.")
        keys=set(segment)-{'blade_row'}
        if keys=={'length'}:curve.segments.append(LineSegmentParameters(**segment))
        elif keys=={'radius','sweep_deg','clockwise'}:curve.segments.append(ArcSegmentParameters(**segment))
        else:raise ValueError("Invalid meridional segment fields.")
    return curve


def load_project(path: str | Path) -> BladeParameters:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Project must be a JSON object.")
    version = data.get("schema_version")
    if version == "0.1":data=migrate_v01_to_v02(data);version="0.2"
    if version == "0.2":data=migrate_v02_to_v03(data);version="0.3"
    if version not in ("0.3","0.4"):raise ValueError(f"Unsupported schema_version: {version!r}")
    return _decode_v03(migrate_v03_blade_edges(migrate_v03_flow_path(data)))


def _decode_v03(data, row_snapshot=False):
    try:
        params = BladeParameters(
            geometry=_group(data, "geometry", GeometryParameters),
            blade_angle=_group(data, "blade_angle", BladeAngleParameters),
            thickness=_group(data, "thickness", ThicknessParameters),
            edges=_group(data, "edges", EdgeParameters),
            output_points=_group(data, "output_points", OutputPointParameters),
            export=_group(data, "export", ExportParameters),
            surface_mapping=SurfaceMapping(data["surface_mapping"]),
            rotation_direction=RotationDirection(data.get("rotation_direction","ccw")))
        if "cad_export" in data:
            from ..models.cad import CadExportParameters,FilletParameters,DiskGeometryParameters,FilletMode,MechanicalExportScope
            values=data["cad_export"]
            if not isinstance(values,dict) or set(values)-{f.name for f in fields(CadExportParameters)}:raise ValueError("Invalid CAD settings fields.")
            values=dict(values)
            fillet=dict(values.pop("fillet",{}));fillet["mode"]=FilletMode(fillet.get("mode","true_cad"))
            disk=dict(values.pop("disk",{}))
            if disk.get("backside") is not None:disk["backside"]=_curve(disk["backside"])
            values["mechanical_scope"]=MechanicalExportScope(values.get("mechanical_scope","blade_hub"))
            params.cad_export=CadExportParameters(**values,fillet=FilletParameters(**fillet),disk=DiskGeometryParameters(**disk))
        params.impeller_te_rake_deg=data.get("impeller_te_rake_deg")
        if data.get('impeller_trim') is not None:
            from ..models.parameters import ImpellerTrimParameters
            params.impeller_trim=_group(data,'impeller_trim',ImpellerTrimParameters)
        if data.get("tip_clearance") is not None:
            from ..models.parameters import TipClearanceParameters
            params.tip_clearance=_group(data,"tip_clearance",TipClearanceParameters)
        if data.get("splitter") is not None:
            values=data["splitter"]
            required={"hub_start_fraction","tip_start_fraction","pitch_fraction","thickness_scale"}
            if not isinstance(values,dict) or not required<=set(values) or set(values)-required-{"sections"}:
                raise ValueError("Invalid splitter fields.")
            params.splitter=SplitterParameters(**values)
            if params.splitter.sections is not None:
                if not isinstance(params.splitter.sections,list):raise ValueError("Invalid splitter sections.")
                profiles=[]
                for v in params.splitter.sections:
                    edge=EdgeParameters(**v["edge_parameters"])
                    edge.le_type,edge.te_type=EdgeType(edge.le_type),EdgeType(edge.te_type)
                    profiles.append(BladeSection(v["span"],
                        BladeAngleParameters([DistributionPoint(**point) for point in v["blade_angle"]["points"]]),
                        ThicknessParameters([DistributionPoint(**point) for point in v["thickness"]["points"]]),edge))
                params.splitter.sections=profiles
        for distribution in (params.blade_angle, params.thickness):
            distribution.points = [DistributionPoint(**p) for p in distribution.points]
        params.edges.le_type = EdgeType(params.edges.le_type)
        params.edges.te_type = EdgeType(params.edges.te_type)
        legacy=(params.blade_angle,params.thickness,params.edges)
        if not isinstance(data.get("sections"),list):raise ValueError("Schema 0.3 requires a section list.")
        if "sections" in data:
            params.sections = []
            for section in data["sections"]:
                angle = BladeAngleParameters([DistributionPoint(**p) for p in section["blade_angle"]["points"]])
                thickness = ThicknessParameters([DistributionPoint(**p) for p in section["thickness"]["points"]])
                edge = EdgeParameters(**section["edge_parameters"])
                edge.le_type,edge.te_type = EdgeType(edge.le_type),EdgeType(edge.te_type)
                params.sections.append(BladeSection(section["span"],angle,thickness,edge))
            if params.sections:
                hub=params.sections[0]
                if (hub.blade_angle,hub.thickness,hub.edge_parameters)!=legacy:
                    raise ValueError("Legacy diffuser fields must match the Hub section in schema 0.3.")
                params.sections[0].blade_angle = params.blade_angle
                params.sections[0].thickness = params.thickness
                params.sections[0].edge_parameters = params.edges
        from copy import deepcopy
        if "diffuser_profile" in data:
            values=data["diffuser_profile"]
            if not isinstance(values,dict) or set(values)!={f.name for f in fields(BladeSection)}:
                raise ValueError("Invalid diffuser profile fields.")
            angle=BladeAngleParameters([DistributionPoint(**v) for v in values["blade_angle"]["points"]])
            thickness=ThicknessParameters([DistributionPoint(**v) for v in values["thickness"]["points"]])
            edges=EdgeParameters(**values["edge_parameters"])
            edges.le_type,edges.te_type=EdgeType(edges.le_type),EdgeType(edges.te_type)
            if values["span"]!=0:raise ValueError("The radial diffuser profile requires span 0.")
            params.diffuser_profile=BladeSection(0.,angle,thickness,edges)
        else:
            # Earlier projects used Hub distributions for both components.
            params.diffuser_profile=deepcopy(params.sections[0])
        params.hub=_curve(data['hub']);params.shroud=_curve(data['shroud'])

        params.turbogrid=_group(data,'turbogrid',TurboGridParameters)
        params.blade_le_fraction=data['blade_le_fraction'];params.blade_te_fraction=data['blade_te_fraction']
        if "flow_path" in data:
            if set(data["flow_path"])!={"stations","align_blade_stations_to_crossflow"} or not isinstance(data["flow_path"]["stations"],list):
                raise ValueError("Invalid flow path fields.")
            if any(set(station)!={"kind","m_flow_norm"} for station in data["flow_path"]["stations"]):
                raise ValueError("Invalid component station fields.")
            params.flow_path=FlowPathParameters([ComponentStation(StationType(v["kind"]),v["m_flow_norm"]) for v in data["flow_path"]["stations"]],data["flow_path"].get("align_blade_stations_to_crossflow",True))
            if params.blade_le_fraction != data['blade_le_fraction'] or params.blade_te_fraction != data['blade_te_fraction']:
                raise ValueError("Legacy LE/TE aliases disagree with component stations.")
        if "resolution" in data:params.resolution=_group(data,"resolution",GeometryResolutionParameters)
        for key in ('impeller_edges','diffuser_edges'):
            row=_group(data,key,BladeRowEdgeParameters)
            row.leading_edge=_group(data[key],'leading_edge',BladeEdgePosition)
            row.trailing_edge=_group(data[key],'trailing_edge',BladeEdgePosition)
            setattr(params,key,row)
        if data.get("blade_rows") is not None:
            from ..models.parameters import BladeRow
            if not isinstance(data["blade_rows"], list):
                raise ValueError("Invalid blade row list.")
            params.blade_rows = []
            for row in data["blade_rows"]:
                if not isinstance(row, dict) or set(row) != {"identifier", "name", "kind", "parameters"}:
                    raise ValueError("Invalid blade row fields.")
                values = row["parameters"]
                if not isinstance(values, dict) or values.get("blade_rows") is not None or values.get("active_blade_row") is not None:
                    raise ValueError("Nested blade row lists are forbidden.")
                params.blade_rows.append(BladeRow(row["identifier"], row["name"], row["kind"], _decode_v03(values, row_snapshot=True)))
        params.active_blade_row = data.get("active_blade_row")
        if params.blade_rows and "tip_clearance" not in data:
            active=next((r for r in params.blade_rows if r.identifier==params.active_blade_row),None)
            if active is not None:params.tip_clearance=deepcopy(active.parameters.tip_clearance)
        _check(params, check_ownership=not row_snapshot)
        return params
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError(f"Malformed v0.3 project: {exc}") from exc
