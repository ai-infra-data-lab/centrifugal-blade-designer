"""Isolated CAD process. It stages files; only the client publishes valid artifacts."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys,os,traceback,hashlib
import numpy as np
from .client import json_text
from .errors import CadGeometryError,InvalidSolidError,FilletGenerationError
from .cad_validation import step_roundtrip,fillet_samples,require_fillet_samples


def execute(job):
    # Avoid importing the numeric engine or Qt in this process.
    from .occt_backend import OcctBackend,shapes
    from OCP.TopAbs import TopAbs_FACE
    request=json.loads((job/"request.json").read_text(encoding="utf-8"));settings=request["settings"]
    report={"geometry_type":"impeller","parameter_snapshot_hash":request["parameter_snapshot_hash"],
        "backend":OcctBackend.name,"backend_version":OcctBackend.version,"cad_unit":"mm","rotation_axis":"Z",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),"worker_pid":os.getpid(),"checks":{},"artifacts":{},
        "mechanical_import":"NOT_TESTED","mechanical_mesh":"NOT_TESTED","turbogrid_import":"NOT_TESTED","turbogrid_mesh":"NOT_TESTED",
        "parasolid":"UNAVAILABLE","step_named_selections":"NOT_GUARANTEED","overall":"FAIL","warnings":[]}
    provisional=settings["disk"].get("provisional",False)
    report["disk_geometry_status"]="PROVISIONAL" if provisional else "USER_SPECIFIED" if settings["disk"]["backside"] is not None else "UNSET"
    if provisional:report["warnings"].append("PROVISIONAL disk dimensions: mechanical front extends 10 mm beyond projected Hub blade roots (limited by wall length), backside 20 mm beyond Hub Z bounds away from Shroud, bore diameter at most 20 mm. Not production disk dimensions; TurboGrid ownership is unchanged.")
    backend=OcctBackend();models=[];current=None;single=None;full=None;stage="surface"
    output=job/"outputs";output.mkdir(exist_ok=True)
    def progress(name):
        nonlocal stage
        stage=name;print("BLADE_CAD:"+json.dumps({"stage":name,"pid":os.getpid()}),flush=True)
    def export(model,relative,root_check=False):
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
        backend.export_step(model,target)
        checked,imported=step_roundtrip(backend,model,target,settings["surface_tolerance_mm"])
        if root_check:
            checked["fillet_before_step"]=fillet_samples(model,settings["fillet"]["hub_radius_mm"])
            checked["fillet_after_step"]=match_fillet_samples(model,imported,settings["fillet"]["hub_radius_mm"],settings["surface_tolerance_mm"])
            require_fillet_samples(checked['fillet_before_step']);require_fillet_samples(checked['fillet_after_step'])
        return {"status":"PASS","files":[relative],"sha256":{relative:hashlib.sha256(target.read_bytes()).hexdigest()},"roundtrip":checked,"surface_roles":backend.surface_roles(model)}
    try:
        if request['action']=='disk':
            progress("PROVISIONAL DISK / NO ROOT FILLET")
            disk=settings['disk']
            if disk['backside'] is None or disk['bore_radius_mm'] is None:raise InvalidSolidError('Disk dimensions are unset.')
            if request.get('domain_error') and not provisional:raise InvalidSolidError(request['domain_error'])
            current=backend.create_hub_solid(request['mechanical_hub_segments'] if provisional else request['hub_segments'],request['backside_segments'],disk['bore_radius_mm'])
            report['checks']['hub_solid']=backend.validate_solid(current)
            report['solid_validity']='PASS';report['fillet_status']='NOT_APPLICABLE (disk only)'
            report['artifacts']['disk_only']=export(current,'mechanical/provisional_disk_NO_FILLET.step')
            report['warnings'].append('Disk-only preview: no blade union or root fillet has been generated.')
            report['overall']='WARNING'
            return report
        progress("SURFACES / BLADE SOLIDS")
        with np.load(job/"geometry.npz",allow_pickle=False) as arrays:
            for group in request["groups"]:
                sections=[]
                for i,span in enumerate(group["spans"]):
                    section={"span":span,**{key+"_type":value for key,value in group.get("edge_types",[{"le":"circular","te":"circular"}]*len(group["spans"]))[i].items()}}
                    for role in ("le","ps","te","ss"):
                        prefix=f'{group["name"]}_{i}_{role}';section[role]=arrays[prefix];section[role+"_xi"]=arrays[prefix+"_xi"]
                    sections.append(section)
                needs_root=settings['mechanical_scope']!='blade_only'
                extension=max(.1,20*settings['surface_tolerance_mm']) if needs_root else 0.
                blade=backend.create_blade_solid(sections,settings["surface_tolerance_mm"],extension)
                models.append((group["name"],blade,sections))
        report["checks"]["blade_solids"]={name:{**backend.validate_solid(model),**model.metrics} for name,model,_ in models}
        report["cad_surface_status"]="PASS";report["blade_solid_status"]="PASS"
        current=models[0][1]
        scope=settings["mechanical_scope"];action=request["action"]
        mech=action in ("mechanical","both") and settings["mechanical_enabled"]
        turbo=action in ("turbogrid","both") and settings["turbogrid_enabled"]
        if not settings["step_enabled"] and (mech or turbo):raise InvalidSolidError("STEP output is disabled in CAD settings.")
        if scope=="blade_only":
            report["warnings"].append("Blade Only contains no disk/root fillet and is not a completed Mechanical R8 assembly.")
            if mech:
                files=[];checks={};hashes={}
                for name,model,_ in models:
                    artifact=export(model,f"mechanical/blade_only_{name}_NO_FILLET.step");files+=artifact["files"];checks[name]=artifact["roundtrip"];hashes.update(artifact["sha256"])
                report["artifacts"]["mechanical"]={"status":"PASS","files":files,"roundtrip":checks,"sha256":hashes,"scope":"blade_only_no_fillet"}
        need_disk=scope!="blade_only" or turbo
        fillet=settings["fillet"];apply_fillet=fillet["hub_enabled"] and fillet["mode"]=="true_cad"
        report.update(hub_fillet_enabled=fillet["hub_enabled"],hub_fillet_radius_mm=fillet["hub_radius_mm"],shroud_fillet_enabled=False)
        if need_disk:
            progress("HUB DISK")
            if request["backside_segments"] is None or settings["disk"]["bore_radius_mm"] is None:
                raise InvalidSolidError("Disk backside and bore radius are unset. Only Blade Only is available; no disk dimensions were inferred.")
            if request.get("domain_error") and not provisional:raise InvalidSolidError("Assigned hub/shroud domain is invalid: "+request["domain_error"])
            hub_segments=request.get("mechanical_hub_segments") if provisional else request["hub_segments"]
            hub=backend.create_hub_solid(hub_segments,request["backside_segments"],settings["disk"]["bore_radius_mm"])
            report["checks"]["hub_solid"]=backend.validate_solid(hub)
            single=hub;extensions={};fillet_data={};features=[];pair_checks=[];construction_models=[]
            for name,blade,sections in models:
                if not blade.metrics.get('root_extension_span_fraction',0):
                    blade=backend.create_blade_solid(sections,settings['surface_tolerance_mm'],
                        max(.1,20*settings['surface_tolerance_mm']))
                construction_models.append((name,blade,sections))
                progress("BOOLEAN UNION / "+name)
                blade.labels['BLADE_GROUP_'+name]=[face for role in ('LE','PS','TE','SS')
                    for face in blade.labels.get('BLADE_'+role,[])]
                united=backend.boolean_union(blade,hub);current=united
                extensions[name]=blade.metrics.get('root_extension_reference_mm',0.)
                feature=backend.subtract(blade,hub)
                for previous_name,previous in features:
                    overlap=backend.check_pair_interference(previous,feature,settings["surface_tolerance_mm"])
                    pair_checks.append({"pair":[previous_name,name],"status":"PASS","overlap_volume_mm3":overlap})
                features.append((name,feature))
                progress('ASSEMBLY UNION / '+name)
                single=united if len(features)==1 else backend.boolean_union(united,single)
            if apply_fillet:
                progress('ROOT EDGE CLASSIFICATION / assembly')
                roots=backend.root_edges(single);current=single
                progress('TRUE CAD FILLET / assembly')
                single=backend.apply_fillet(single,roots,fillet['hub_radius_mm']);current=single
                report['checks']['root_group_surface_separation']=backend.check_root_group_separation(single,settings['surface_tolerance_mm'])
                from .occt_backend import CadShape
                for name,blade,_ in construction_models:
                    group_labels={'HUB_FILLET':single.labels.get('HUB_FILLET_GROUP_'+name,[]),
                        'HUB_FILLET_ROLLING':single.labels.get('HUB_FILLET_ROLLING_GROUP_'+name,[]),
                        'HUB_FILLET_CORNER':single.labels.get('HUB_FILLET_CORNER_GROUP_'+name,[])}
                    measured=fillet_samples(CadShape(single.shape,group_labels),fillet['hub_radius_mm'])
                    require_fillet_samples(measured)
                    fillet_data[name]={**single.metrics,**single.metrics['fillet_groups'][name],
                        'root_extension_reference_mm':extensions[name],
                        'root_extension_span_fraction':blade.metrics['root_extension_span_fraction'],
                        'root_cap_inside_hub':True,'radius_measurements':measured}
            report["checks"].update(root_extension_mm=extensions,fillet=fillet_data,within_passage_interference=pair_checks)
            report["boolean_status"]="PASS";report["fillet_status"]="PASS" if apply_fillet else "NOT_REQUESTED"
            progress("INTER-BLADE INTERFERENCE")
            feature=backend.subtract(single,hub)
            report["checks"].update(backend.check_interference(feature,int(request["blade_count"]),settings["surface_tolerance_mm"]))
            report["checks"]["single_assembly"]=backend.validate_solid(single)
            current=single;full=None
            suffix=("R"+format(fillet["hub_radius_mm"],"g")) if apply_fillet else "NO_FILLET"
            if mech and scope=="blade_hub":
                progress("MECHANICAL STEP / ROUND TRIP")
                report["artifacts"]["mechanical"]=export(single,f'mechanical/impeller_{scope}_{suffix}.step',apply_fillet)
            if turbo and request.get("domain_error") and scope in ("blade_only","blade_hub"):
                progress("TURBOGRID FLOW BOUNDARY CAD")
                raise InvalidSolidError("Assigned hub/shroud domain is invalid for TurboGrid: "+request["domain_error"])
            if scope in ("full_impeller","periodic_sector") or turbo:
                progress("FULL IMPELLER")
                full=backend.full_impeller(single,hub,int(request["blade_count"]),settings["surface_tolerance_mm"],check_interference=False)
                report["checks"]["full_impeller"]=backend.validate_solid(full)
            mechanical=models[0][1] if scope=="blade_only" else full if scope=="full_impeller" else backend.sector(full,int(request["blade_count"])) if scope=="periodic_sector" else single
            current=mechanical
            suffix=("R"+format(fillet["hub_radius_mm"],"g")) if apply_fillet else "NO_FILLET"
            if mech and scope not in ("blade_only","blade_hub"):
                progress("MECHANICAL STEP / ROUND TRIP")
                report["artifacts"]["mechanical"]=export(mechanical,f'mechanical/impeller_{scope}_{suffix}.step',apply_fillet)
            if turbo:
                progress("TURBOGRID FLOW BOUNDARY CAD")
                if request.get("domain_error"):raise InvalidSolidError("Assigned hub/shroud domain is invalid for TurboGrid: "+request["domain_error"])
                passage=backend.create_flow_passage(request["hub_segments"],request["shroud_segments"])
                fluid=backend.sector(backend.subtract(passage,full),int(request["blade_count"]))
                required={"HUB","SHROUD","BLADE_PS","BLADE_SS","BLADE_LE","BLADE_TE","INLET","OUTLET"}
                if apply_fillet:required.add("HUB_FILLET")
                if request["blade_count"]>1:required.update(("PERIODIC_LOW","PERIODIC_HIGH"))
                labels={name:len(faces) for name,faces in fluid.labels.items() if faces}
                if required-set(labels):raise InvalidSolidError("Missing TurboGrid boundary roles: "+str(sorted(required-set(labels))))
                artifact=export(fluid,"turbogrid/cad/turbogrid_cad.step")
                artifact.update(status="CONVERSION_REQUIRED",boundary_roles=labels,description="Validated fluid passage STEP, not the mechanical disk. Convert to a format supported by the target TurboGrid release; direct import is NOT_TESTED.")
                report["artifacts"]["turbogrid_cad"]=artifact
                report["warnings"].append("Parasolid writer/converter unavailable; STEP is an intermediate CAD artifact, not verified direct TurboGrid input.")
        else:
            report["fillet_status"]="NOT_APPLICABLE"
            report["checks"]["inter_blade_interference"]="NOT_TESTED (blade-only inspection, no assembly)"
        report["solid_validity"]="PASS";report["checks"]["result"]=backend.validate_solid(current)
        report["overall"]="WARNING" if report["warnings"] else "PASS"
    except Exception as exc:
        from .errors import SurfaceConstructionError,BooleanUnionError,CadExportError
        category=type(exc).__name__
        if not isinstance(exc,CadGeometryError):
            category=(SurfaceConstructionError if "SURFACES" in stage else FilletGenerationError if "FILLET" in stage or "ROOT" in stage else CadExportError if "STEP" in stage else BooleanUnionError if "UNION" in stage else InvalidSolidError).__name__
        report["error"]={"stage":stage,"type":category,"kernel_exception":type(exc).__name__,"message":str(exc)}
        (job/"error.log").write_text(traceback.format_exc(),encoding="utf-8")
        # Any artifact already validated remains valid; incomplete ones are never published.
        if current is not None:
            try:
                debug=job/"debug";debug.mkdir(exist_ok=True);backend.export_step(current,debug/"NO_FILLET_OR_INCOMPLETE.step")
                report["debug_model"]="debug/NO_FILLET_OR_INCOMPLETE.step"
            except Exception:pass
    finally:
        if current is not None:
            try:
                preview={"triangles":backend.triangulate(current),"edges":backend.edge_polylines(current),
                    "fillet_radius_mm":settings["fillet"]["hub_radius_mm"],"snapshot_hash":report["parameter_snapshot_hash"],
                    "scope":"disk_only" if request['action']=='disk' else settings["mechanical_scope"],"blade_count":request["blade_count"]}
                if single is not None:preview["triangles_single"]=backend.triangulate(single)
                if full is not None:preview["triangles_full"]=backend.triangulate(full)
                (job/"preview.json").write_text(json_text(preview),encoding="utf-8")
            except Exception as exc:report["warnings"].append("CAD preview failed: "+str(exc))
        (job/"result.json").write_text(json_text(report),encoding="utf-8")
    return report


def match_fillet_samples(original,imported,radius,tolerance):
    from .occt_backend import shapes
    from OCP.TopAbs import TopAbs_FACE
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopoDS import TopoDS
    from .cad_validation import trimmed_face_parameters
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    target_faces_with_bounds=[]
    for target_face in shapes(imported.shape,TopAbs_FACE):
        box=Bnd_Box();BRepBndLib.AddOptimal_s(target_face,box,False,True)
        box.Enlarge(tolerance)
        target_faces_with_bounds.append((target_face,box))
    rolling=original.labels.get('HUB_FILLET_ROLLING',original.labels.get('HUB_FILLET',[]))
    groups=[('HUB_FILLET_ROLLING',rolling),('HUB_FILLET_CORNER',original.labels.get('HUB_FILLET_CORNER',[]))]
    all_matches=[]
    for name,faces in groups:
        matches=[]
        for face in faces:
            surface=BRep_Tool.Surface_s(TopoDS.Face(face))
            source_parameters=trimmed_face_parameters(face,(.5,.25,.75,.1,.9),max_points=1)
            point=surface.Value(*source_parameters[0]) if source_parameters else None
            if point is None:raise InvalidSolidError("Cannot sample the trimmed root fillet face.")
            vertex=BRepBuilderAPI_MakeVertex(point).Vertex();distances=[]
            for target_face,box in target_faces_with_bounds:
                if box.IsOut(point):continue
                distance=BRepExtrema_DistShapeShape(vertex,target_face)
                if not distance.IsDone():raise InvalidSolidError('STEP fillet face distance evaluation failed.')
                value=distance.Value()
                if not np.isfinite(value):raise InvalidSolidError('Non-finite STEP fillet face distance.')
                distances.append((value,target_face))
            if not distances:raise InvalidSolidError('No imported face lies within the fillet matching bounds.')
            distance,nearest=min(distances,key=lambda item:item[0])
            if distance<=tolerance:matches.append(nearest)
        if len(matches)!=len(faces):raise InvalidSolidError("Root fillet faces could not all be matched after STEP import.")
        imported.labels[name]=matches;all_matches.extend(matches)
    if not all_matches:raise InvalidSolidError('No rolling fillet faces were matched after STEP import.')
    imported.labels["HUB_FILLET"]=all_matches
    return fillet_samples(imported,radius)


def main():
    job=Path(sys.argv[1]).resolve()
    try:report=execute(job)
    except Exception as exc:
        report={"overall":"FAIL","error":{"type":type(exc).__name__,"message":str(exc)},"artifacts":{}}
        (job/"result.json").write_text(json_text(report),encoding="utf-8")
    print("BLADE_CAD:"+json.dumps({"finished":True,"status":report["overall"]}),flush=True)
    return 0

if __name__=="__main__":raise SystemExit(main())
