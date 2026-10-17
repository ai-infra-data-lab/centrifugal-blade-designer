"""Measured CAD and STEP checks. No unexecuted check is marked PASS."""
from pathlib import Path
import re
import numpy as np
from .errors import CadExportError


def step_roundtrip(backend,model,path,tolerance_mm):
    path=Path(path)
    if not path.is_file() or path.stat().st_size==0:raise CadExportError("STEP file is missing or empty.")
    source=backend.validate_solid(model);imported=backend.read_step(path);actual=backend.validate_solid(imported)
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
    bbox_difference=float(np.max(np.abs(np.array(source["bbox_mm"])-actual["bbox_mm"])))
    if max(source["max_edge_tolerance_mm"],actual["max_edge_tolerance_mm"])>tolerance_mm:raise CadExportError("STEP edge/gap tolerance exceeds the specified CAD tolerance.")
    if not units or source["solid_count"]!=actual["solid_count"] or difference>volume_tolerance or bbox_difference>dimension_tolerance:
        raise CadExportError(f"STEP round trip failed: mm={units}, volume difference={difference:g} (limit {volume_tolerance:g}), bbox difference={bbox_difference:g} (limit {dimension_tolerance:g}).")
    return {"status":"PASS","units_mm":"PASS","original":source,"imported":actual,
        "volume_difference_mm3":difference,"volume_tolerance_mm3":volume_tolerance,
        "bbox_max_difference_mm":bbox_difference,"bbox_tolerance_mm":dimension_tolerance,
        "bbox_tolerance_basis":"Measured source + imported edge tolerances, bounded by requested CAD tolerance; precision floor is max(1e-7, CAD tolerance * .01)."},imported


def fillet_samples(model,radius_mm):
    from OCP.BRep import BRep_Tool
    from OCP.BRepTools import BRepTools
    from OCP.GeomLProp import GeomLProp_SLProps
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.TopAbs import TopAbs_IN,TopAbs_ON
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt2d
    result=[]
    for face in model.labels.get("HUB_FILLET",[]):
        face=TopoDS.Face(face);surface=BRep_Tool.Surface_s(face);u0,u1,v0,v1=BRepTools.UVBounds_s(face)
        measurements=[]
        for a in (.25,.5,.75):
            for b in (.25,.5,.75):
                u=u0+a*(u1-u0);v=v0+b*(v1-v0)
                if BRepClass_FaceClassifier(face,gp_Pnt2d(u,v),1e-7).State() not in (TopAbs_IN,TopAbs_ON):continue
                props=GeomLProp_SLProps(surface,u,v,2,1e-8)
                if not props.IsCurvatureDefined():continue
                values=[abs(1/k) for k in (props.MaxCurvature(),props.MinCurvature()) if abs(k)>1e-10]
                if values:measurements.append(min(values,key=lambda value:abs(value-radius_mm)))
        result.append({"sampled_principal_radii_mm":measurements,"status":"PASS" if measurements and all(abs(r-radius_mm)<=max(.01,radius_mm*.005) for r in measurements) else "WARNING"})
    return {"requested_radius_mm":radius_mm,"faces":result,"global_exact_radius":"NOT_TESTED",
        "note":"Principal curvature samples supplement kernel fillet success; they do not prove the radius at every point."}
