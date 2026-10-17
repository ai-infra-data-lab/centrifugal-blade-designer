"""Prepare immutable numeric snapshots without importing CAD libraries or Qt."""
from pathlib import Path
from dataclasses import asdict
from copy import deepcopy
import hashlib,json,sys,uuid
import numpy as np
from ..models.cad import validate_cad_parameters
from ..models.blade_rows import row_parameters,validate_rows
from ..geometry.geometry_3d import generate_impeller
from ..geometry.meridional_segments import generate_meridional,sample_meridional
from ..geometry.row_domain import export_wall_intervals
from ..models.meridional import ArcSegmentGeometry
from .errors import BackendUnavailableError

ROOT=Path(__file__).resolve().parents[2]


def json_text(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,indent=2,
        default=lambda v:v.value if hasattr(v,"value") else v.item())+"\n"


def backend_python():
    path=ROOT/".venv-cad"/("Scripts/python.exe" if sys.platform=="win32" else "bin/python")
    if not path.is_file():raise BackendUnavailableError("CAD backend is unavailable. Create .venv-cad and install requirements-cad.txt; coordinate editing is still available.")
    return path


def segment_points(curve,start=0.,end=None):
    end=curve.length if end is None else end;distance=0.;result=[]
    for segment in curve.segments:
        a,b=max(start,distance),min(end,distance+segment.length)
        if b>a+1e-10:
            coordinates=[a,(a+b)/2,b] if isinstance(segment,ArcSegmentGeometry) else [a,b]
            result.append(sample_meridional(curve,np.array(coordinates)).tolist())
        distance+=segment.length
    return result


def prepare_job(project,action="generate",job_directory=None):
    project=deepcopy(project);validate_rows(project);params=project
    if project.blade_rows is not None:
        row=next(row for row in project.blade_rows if row.identifier==project.active_blade_row)
        if row.kind!="impeller":raise ValueError("CAD export currently requires an Impeller blade row.")
        params=row_parameters(project,row)
    from ..fileio.trim_export_guard import guard_trim_export
    guard_trim_export(params)
    validate_cad_parameters(params.cad_export)
    from ..geometry.tip_clearance import has_tip_clearance
    if has_tip_clearance(params) and action in ('turbogrid','both') and params.cad_export.turbogrid_enabled:
        raise ValueError('Open-impeller Tip clearance TurboGrid CAD export is not supported yet. No output was written.')
    geometry=generate_impeller(params)
    domain_error=None
    try:intervals=export_wall_intervals(project,geometry,params.impeller_edges)
    except ValueError as exc:
        # A blade-only inspection must not depend on a wall export assignment.
        # Structural/flow CAD is still blocked by this recorded error.
        domain_error=str(exc);intervals=((0.,geometry.hub.length),(0.,geometry.shroud.length))
    job=Path(job_directory) if job_directory is not None else ROOT/"artifacts"/"cad-runs"/uuid.uuid4().hex
    job.mkdir(parents=True,exist_ok=False)
    snapshot={"schema_version":"0.4",**asdict(project)}
    text=json_text(snapshot);(job/"geometry_snapshot.json").write_text(text,encoding="utf-8")
    arrays={};groups=[]
    for name,sections in (("main",geometry.sections),("splitter",geometry.splitter_sections)):
        if sections is None:continue
        groups.append({"name":name,"spans":[float(s.span) for s in sections],"edge_types":[{"le":s.edge_parameters.le_type.value,"te":s.edge_parameters.te_type.value} for s in params.sections]})
        for index,section in enumerate(sections):
            for role in ("le","ps","te","ss"):
                curve=getattr(section,"master_"+role);prefix=f"{name}_{index}_{role}"
                arrays[prefix]=curve.xyz
                parameter=curve.m_blade_norm
                if parameter is None:parameter=np.linspace(0,1,len(curve.r))
                parameter=np.asarray(parameter,dtype=float)
                if np.any(np.diff(parameter)<=0):raise ValueError("CAD profile correspondence is not strictly increasing: "+prefix)
                arrays[prefix+"_xi"]=(parameter-parameter[0])/(parameter[-1]-parameter[0])
    np.savez_compressed(job/"geometry.npz",**arrays)
    disk=params.cad_export.disk
    mechanical_hub_segments=None
    if disk.provisional:
        from ..geometry.provisional_disk import hub_blade_extent
        end=disk.front_end_m_mm
        maximum=hub_blade_extent(geometry)
        if end>geometry.hub.length+1e-9 or end<maximum-geometry.hub.length*1e-6:
            raise ValueError("仮ディスクの前面範囲が現在のHub翼形状に合いません。仮ディスク寸法を再作成してください。")
        mechanical_hub_segments=segment_points(geometry.hub,0.,min(end,geometry.hub.length))
    request={"action":action,"parameter_snapshot_hash":hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "groups":groups,"domain_error":domain_error,"settings":asdict(params.cad_export),"blade_count":params.geometry.vane_count,
        "mechanical_hub_segments":mechanical_hub_segments,
        "hub_segments":segment_points(geometry.hub,*intervals[0]),"shroud_segments":segment_points(geometry.shroud,*intervals[1]),
        "backside_segments":None if disk.backside is None else segment_points(generate_meridional(disk.backside))}
    (job/"request.json").write_text(json_text(request),encoding="utf-8")
    return job


def publish_job(job,target,project):
    """Keep partial successes distinct and protect existing valid files on failure."""
    from ..fileio.mechanical_step_export import publish_verified_artifact
    from ..fileio.turbogrid_export import export_turbogrid
    from ..fileio.turbogrid_cad_export import TURBOGRID_CAD_INSTRUCTIONS,blade_blend_instructions
    from ..fileio.cad_validation_report import write_report
    job=Path(job);target=Path(target)
    request=json.loads((job/"request.json").read_text(encoding="utf-8"));report=json.loads((job/"result.json").read_text(encoding="utf-8"))
    expected=hashlib.sha256(json_text({"schema_version":"0.4",**asdict(project)}).encode("utf-8")).hexdigest()
    if expected!=request["parameter_snapshot_hash"] or report.get("parameter_snapshot_hash",expected)!=expected:raise ValueError("CAD snapshot hash mismatch; no files published.")
    requested=[];action=request["action"];settings=request["settings"]
    if action in ("mechanical","both") and settings["mechanical_enabled"]:requested.append("mechanical")
    if action in ("turbogrid","both") and settings["turbogrid_enabled"]:requested.extend(("turbogrid_profile_points","turbogrid_cad"))
    for name,artifact in report.get("artifacts",{}).items():
        if artifact.get("status") in ("PASS","CONVERSION_REQUIRED"):
            try:publish_verified_artifact(job,target,artifact)
            except Exception as exc:artifact.update(status="FAIL",error=str(exc));report["overall"]="FAIL"
    if "turbogrid_profile_points" in requested:
        try:
            files=export_turbogrid(target/"turbogrid"/"profile_points",project)
            report.setdefault("artifacts",{})["turbogrid_profile_points"]={"status":"PASS","files":[str(p.relative_to(target)) for p in files],"root_fillet_included":False}
        except Exception as exc:report.setdefault("artifacts",{})["turbogrid_profile_points"]={"status":"FAIL","error":str(exc)}
    for name in requested:report.setdefault("artifacts",{}).setdefault(name,{"status":"FAIL","error":report.get("error",{}).get("message","Artifact was not generated.")})
    if any(report["artifacts"][name]["status"]=="FAIL" for name in requested):report["overall"]="FAIL"
    target.mkdir(parents=True,exist_ok=True)
    if report.get("artifacts",{}).get("mechanical",{}).get("status")=="PASS":
        directory=target/"mechanical";directory.mkdir(exist_ok=True)
        (directory/"import_instructions.md").write_text("# Mechanical STEP import (NOT_TESTED)\n\nWorkbench: add Static Structural, import the STEP into Geometry, open Mechanical, check solid count and units (mm, axis Z), inspect the root fillet if present, and attempt meshing. For a periodic sector check cyclic faces. Blade Only/NO_FILLET is not a completed root-filleted assembly. Compare the validation report and snapshot hash. No ANSYS import or mesh was run.\n",encoding="utf-8")
    turbo_directory=target/"turbogrid";turbo_directory.mkdir(exist_ok=True)
    fillet=settings['fillet']
    (turbo_directory/"blade_blend_settings.md").write_text(blade_blend_instructions(fillet['hub_radius_mm'],fillet['hub_enabled'] and fillet['mode']=='true_cad'),encoding="utf-8")
    if report.get("artifacts",{}).get("turbogrid_cad",{}).get("status")=="CONVERSION_REQUIRED":
        (turbo_directory/"cad"/"cad_import_instructions.md").write_text(TURBOGRID_CAD_INSTRUCTIONS,encoding="utf-8")
    parameters=target/"parameters";parameters.mkdir(exist_ok=True)
    (parameters/("geometry_snapshot_"+expected[:16]+".json")).write_text((job/"geometry_snapshot.json").read_text(encoding="utf-8"),encoding="utf-8")
    if report["overall"]!="FAIL":(parameters/"geometry_snapshot.json").write_text((job/"geometry_snapshot.json").read_text(encoding="utf-8"),encoding="utf-8")
    validation=target/"validation";validation.mkdir(exist_ok=True)
    for name,artifact in report.get("artifacts",{}).items():
        if artifact.get("status") in ("PASS","CONVERSION_REQUIRED") and artifact.get("surface_roles"):
            (validation/(name+"_surface_roles.json")).write_text(json_text({"units":"mm","axis":"Z","roles":artifact["surface_roles"]}),encoding="utf-8")
    write_report(validation,report,job.name if report["overall"]=="FAIL" else None)
    return report
