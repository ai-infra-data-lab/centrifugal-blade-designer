"""Measured CAD and STEP checks. No unexecuted check is marked PASS."""
from pathlib import Path
from numbers import Real,Integral
import math
import re
import numpy as np
from .errors import CadExportError


def _finite_number(value):
    try:return isinstance(value,Real) and not isinstance(value,bool) and math.isfinite(value)
    except (ValueError,TypeError,OverflowError):return False


def _require_step_metrics(metrics):
    if not isinstance(metrics,dict):raise CadExportError('Missing STEP solid measurements.')
    count=metrics.get('solid_count');bounds=metrics.get('bbox_mm')
    try:bounds=list(bounds)
    except TypeError:bounds=[]
    if (not isinstance(count,Integral) or isinstance(count,bool) or count<1 or len(bounds)!=6 or
            not all(_finite_number(value) for value in bounds) or
            any(bounds[i]>=bounds[i+3] for i in range(3))):
        raise CadExportError('Invalid STEP solid count or bounding box measurements.')
    for name in ('volume_mm3','surface_area_mm2','max_edge_tolerance_mm'):
        value=metrics.get(name)
        if not _finite_number(value) or value<0 or (name!='max_edge_tolerance_mm' and value==0):
            raise CadExportError('Invalid or non-finite STEP measurement: '+name)


def require_fillet_samples(measurement):
    """Reject missing/failed/non-finite rolling-radius evidence before publish.

    Uses the existing sampled principal-radius tolerance. Corner transition
    curvature and a global exact-radius proof are separate reported questions.
    """
    from numbers import Real
    radius=measurement.get('requested_radius_mm') if isinstance(measurement,dict) else None
    if not isinstance(radius,Real) or isinstance(radius,bool) or not np.isfinite(radius) or radius<=0:
        raise CadExportError('Invalid requested radius in root fillet measurements.')
    faces=measurement.get('faces')
    if not isinstance(faces,list) or not faces:raise CadExportError('Missing rolling fillet radius samples.')
    tolerance=max(.01,radius*.005)
    for face in faces:
        values=face.get('sampled_principal_radii_mm') if isinstance(face,dict) else None
        if (not isinstance(values,list) or not values or face.get('status')!='PASS' or
                any(not isinstance(v,Real) or isinstance(v,bool) or not np.isfinite(v) or
                    abs(v-radius)>tolerance for v in values)):
            raise CadExportError('Rolling fillet radius samples failed or are incomplete; output was not accepted.')


def step_roundtrip(backend,model,path,tolerance_mm):
    if not _finite_number(tolerance_mm) or tolerance_mm<=0:
        raise CadExportError('A positive finite STEP comparison tolerance is required.')
    path=Path(path)
    if not path.is_file() or path.stat().st_size==0:raise CadExportError("STEP file is missing or empty.")
    source=backend.validate_solid(model);_require_step_metrics(source)
    imported=backend.read_step(path);actual=backend.validate_solid(imported);_require_step_metrics(actual)
    text=path.read_text(encoding="ascii",errors="replace")
    units=bool(re.search(r"SI_UNIT\s*\(\s*\.MILLI\.\s*,\s*\.METRE\.",text))
    comparison_precision=max(1e-7,tolerance_mm*.01)
    # STEP healing may move trim boundaries within their stored BREP tolerances.
    # Compare using that measured error budget, always capped by the requested
    # CAD tolerance. Analytic/precise solids retain the stricter precision floor.
    dimension_tolerance=min(tolerance_mm,max(comparison_precision,
        source["max_edge_tolerance_mm"]+actual["max_edge_tolerance_mm"]))
    volume_tolerance=max(source["volume_mm3"]*1e-7,source["surface_area_mm2"]*comparison_precision)
    difference=abs(actual["volume_mm3"]-source["volume_mm3"])
    with np.errstate(over='ignore',invalid='ignore'):
        bbox_difference=float(np.max(np.abs(np.asarray(source["bbox_mm"],dtype=float)-actual["bbox_mm"])))
    if not all(_finite_number(value) for value in (dimension_tolerance,volume_tolerance,difference,bbox_difference)):
        raise CadExportError('Non-finite derived STEP comparison measurements.')
    if max(source["max_edge_tolerance_mm"],actual["max_edge_tolerance_mm"])>tolerance_mm:raise CadExportError("STEP edge/gap tolerance exceeds the specified CAD tolerance.")
    if not units or source["solid_count"]!=actual["solid_count"] or difference>volume_tolerance or bbox_difference>dimension_tolerance:
        raise CadExportError(f"STEP round trip failed: mm={units}, volume difference={difference:g} (limit {volume_tolerance:g}), bbox difference={bbox_difference:g} (limit {dimension_tolerance:g}).")
    return {"status":"PASS","units_mm":"PASS","original":source,"imported":actual,
        "volume_difference_mm3":difference,"volume_tolerance_mm3":volume_tolerance,
        "bbox_max_difference_mm":bbox_difference,"bbox_tolerance_mm":dimension_tolerance,
        "bbox_tolerance_basis":"Measured source + imported edge tolerances, bounded by requested CAD tolerance; precision floor is max(1e-7, CAD tolerance * .01)."},imported


def trimmed_face_parameters(face,fractions=(.25,.5,.75),max_points=9):
    """Find classified points even on narrow trimmed faces; never relax trims.

    Mesh fallback works on a topology copy and every UV candidate is checked
    against the original exact trim. No accepted candidate means no evidence.
    """
    if type(max_points) is not int or max_points<1:raise ValueError('max_points must be positive.')
    fractions=tuple(fractions)
    if not fractions or not np.isfinite(fractions).all() or any(not 0<=x<=1 for x in fractions):
        raise ValueError('Sampling fractions must be finite and within [0,1].')
    from OCP.BRep import BRep_Tool
    from OCP.BRepTools import BRepTools
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.TopAbs import TopAbs_IN,TopAbs_ON
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt2d
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    face=TopoDS.Face(face);u0,u1,v0,v1=BRepTools.UVBounds_s(face);result=[]
    def accept(u,v):
        if (np.isfinite([u,v]).all() and
                BRepClass_FaceClassifier(face,gp_Pnt2d(float(u),float(v)),1e-7).State() in (TopAbs_IN,TopAbs_ON)):
            result.append((float(u),float(v)))
    for a in fractions:
        for b in fractions:
            accept(u0+a*(u1-u0),v0+b*(v1-v0))
            if len(result)>=max_points:return result
    if result:return result
    surface=BRep_Tool.Surface_s(face)
    try:
        properties=GProp_GProps();BRepGProp.SurfaceProperties_s(face,properties)
        projection=GeomAPI_ProjectPointOnSurf(properties.CentreOfMass(),surface)
        for index in range(1,projection.NbPoints()+1):
            accept(*projection.Parameters(index))
            if len(result)>=max_points:break
    except Exception:
        # A failed auxiliary projection is not evidence; bounded triangulation
        # below must still produce a point accepted by the original trim.
        pass
    if result:return result
    copied=TopoDS.Face(BRepBuilderAPI_Copy(face,False,False).Shape())
    for deflection in (.01,.0001,.000001):
        BRepTools.Clean_s(copied)
        mesher=BRepMesh_IncrementalMesh(copied,deflection,False,.25,False)
        if not mesher.IsDone():continue
        mesh=BRep_Tool.Triangulation_s(copied,TopLoc_Location())
        if mesh is None or not mesh.HasUVNodes():continue
        stride=max(1,int(np.ceil(mesh.NbTriangles()/16384)))
        for index in range(1,mesh.NbTriangles()+1,stride):
            nodes=[mesh.UVNode(i) for i in mesh.Triangle(index).Get()]
            accept(sum(p.X() for p in nodes)/3,sum(p.Y() for p in nodes)/3)
            if len(result)>=max_points:return result
        if result:return result
    return result


def fillet_samples(model,radius_mm):
    from OCP.BRep import BRep_Tool
    from OCP.GeomLProp import GeomLProp_SLProps
    from OCP.TopoDS import TopoDS
    result=[]
    for face in model.labels.get('HUB_FILLET_ROLLING',model.labels.get("HUB_FILLET",[])):
        face=TopoDS.Face(face);surface=BRep_Tool.Surface_s(face)
        measurements=[]
        for u,v in trimmed_face_parameters(face):
            props=GeomLProp_SLProps(surface,u,v,2,1e-8)
            if not props.IsCurvatureDefined():continue
            values=[abs(1/k) for k in (props.MaxCurvature(),props.MinCurvature()) if abs(k)>1e-10]
            if values:measurements.append(min(values,key=lambda value:abs(value-radius_mm)))
        result.append({"sampled_principal_radii_mm":measurements,"status":"PASS" if measurements and all(abs(r-radius_mm)<=max(.01,radius_mm*.005) for r in measurements) else "WARNING"})
    return {"requested_radius_mm":radius_mm,"faces":result,"global_exact_radius":"NOT_TESTED",
        "measurement_scope":"kernel edge-generated rolling faces; corner transitions have variable principal curvatures",
        "corner_faces":len(model.labels.get('HUB_FILLET_CORNER',[])),"corner_radius_check":"NOT_APPLICABLE",
        "corner_continuity":"NOT_TESTED",
        "note":"Principal curvature samples supplement kernel fillet success; they do not prove the radius at every point."}
