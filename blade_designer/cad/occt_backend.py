"""Open CASCADE BREP backend; imported only by the isolated CAD worker."""
from dataclasses import dataclass,field
from importlib.metadata import version
import numpy as np
from OCP.collections import Array2_gp_Pnt
from OCP.gp import gp_Pnt,gp_Dir,gp_Ax1,gp_Trsf
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeFace,BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_Sewing,BRepBuilderAPI_MakePolygon,BRepBuilderAPI_Transform)
from OCP.BRepFill import BRepFill_Filling
from OCP.GeomAbs import GeomAbs_C0
from OCP.ShapeFix import ShapeFix_Solid
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_SHELL,TopAbs_SOLID,TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAlgoAPI import BRepAlgoAPI_Check,BRepAlgoAPI_Fuse,BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.STEPControl import STEPControl_Writer,STEPControl_Reader,STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from .errors import SurfaceConstructionError,InvalidSolidError,CadExportError,BooleanUnionError,FilletGenerationError


def shapes(shape,kind):
    iterator=TopExp_Explorer(shape,kind);result=[]
    while iterator.More():result.append(iterator.Current());iterator.Next()
    return result

@dataclass
class CadShape:
    shape:object
    labels:dict=field(default_factory=dict)
    metrics:dict=field(default_factory=dict)
    root_edge_tags:list=field(default_factory=list)


class OcctBackend:
    name="Open CASCADE / cadquery-ocp"
    version=version("cadquery-ocp")

    def create_surface(self,rows,count,parameters=None,spans=None,tangents=None):
        from ..geometry.surface_evaluation import fit_surface_spline
        from OCP.Geom import Geom_BSplineSurface
        from OCP.collections import Array1_double,Array1_int
        numeric=fit_surface_spline(rows,count,parameters or None,spans,tangents)
        along,across=numeric.along,numeric.across
        # scipy coefficients are (span pole, streamwise pole, xyz).
        poles=across.c
        grid=Array2_gp_Pnt(1,poles.shape[0],1,poles.shape[1])
        for i in range(poles.shape[0]):
            for j in range(poles.shape[1]):grid.SetValue(i+1,j+1,gp_Pnt(*map(float,poles[i,j])))
        def knots(values):
            unique,multiplicity=np.unique(values,return_counts=True)
            u=Array1_double(1,len(unique));m=Array1_int(1,len(unique))
            for i,(value,count_) in enumerate(zip(unique,multiplicity),1):u.SetValue(i,float(value));m.SetValue(i,int(count_))
            return u,m
        uk,um=knots(across.t);vk,vm=knots(along.t)
        return Geom_BSplineSurface(grid,uk,vk,um,vm,across.k,along.k)

    def create_blade_solid(self,sections,tolerance_mm):
        surfaces={};faces={};deviations={};counts={}
        tangents=self._join_tangents(sections)
        for name in ("le","ps","te","ss"):
            rows=[np.asarray(section[name],dtype=float) for section in sections]
            if any(row.ndim!=2 or row.shape[1]!=3 or len(row)<2 or not np.isfinite(row).all() for row in rows):
                raise SurfaceConstructionError("Invalid "+name+" coordinates.")
            parameters=[np.asarray(section.get(name+"_xi",np.linspace(0,1,len(row)))) for section,row in zip(sections,rows)]
            spans=[section.get("span",i/(len(sections)-1)) for i,section in enumerate(sections)]
            # Adaptive density, checked at corresponding parameters of every master point.
            for count in (33,65,129,257,513):
                try:
                    surface=self.create_surface(rows,count,parameters,spans,tangents.get(name))
                    distance=0.
                    u0,u1,v0,v1=surface.Bounds()
                    for index,row in enumerate(rows):
                        u=float(spans[index])
                        for fraction,point in zip(parameters[index],row):
                            actual=surface.Value(u,v0+(v1-v0)*fraction)
                            distance=max(distance,float(np.linalg.norm(np.array([actual.X(),actual.Y(),actual.Z()])-point)))
                    if distance<=tolerance_mm:break
                except Exception as exc:
                    raise SurfaceConstructionError(f"{name.upper()} surface: {exc}") from exc
            else:raise SurfaceConstructionError(f"{name.upper()} deviation {distance:g} exceeds {tolerance_mm:g} mm.")
            face=BRepBuilderAPI_MakeFace(surface,tolerance_mm*.01)
            if not face.IsDone():raise SurfaceConstructionError(name+" face failed.")
            surfaces[name]=surface;faces[name]=face.Face();deviations[name]=distance;counts[name]=count
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire
        caps=[];cap_methods=[]
        for side in (0,1):
            edges=[]
            for surface in surfaces.values():
                bounds=surface.Bounds();edges.append(BRepBuilderAPI_MakeEdge(surface.UIso(bounds[side])).Edge())
            wire=BRepBuilderAPI_MakeWire()
            for edge in edges:wire.Add(edge)
            # Preserve an exact planar cap instead of fitting a high-degree
            # surface to a plane; curved meridional walls still need filling.
            plane=BRepBuilderAPI_MakeFace(wire.Wire(),True) if wire.IsDone() else None
            if plane is not None and plane.IsDone():
                caps.append(plane.Face());cap_methods.append("plane");continue
            filling=BRepFill_Filling(Tol3d=tolerance_mm*.01,NbPtsOnCur=30,NbIter=3,MaxDeg=12,MaxSegments=64)
            for edge in edges:filling.Add(edge,GeomAbs_C0)
            filling.Build()
            if not filling.IsDone():raise SurfaceConstructionError(("Hub" if side==0 else "Tip")+" cap filling failed.")
            caps.append(filling.Face());cap_methods.append("filling")
        sewing=BRepBuilderAPI_Sewing(tolerance_mm*.1)
        for face in [*faces.values(),*caps]:sewing.Add(face)
        sewing.Perform();shells=shapes(sewing.SewedShape(),TopAbs_SHELL)
        if len(shells)!=1:raise InvalidSolidError(f"Expected one closed shell, got {len(shells)}.")
        shell=TopoDS.Shell(shells[0])
        if not BRep_Tool.IsClosed_s(shell):raise InvalidSolidError("Blade shell is not watertight.")
        solid=ShapeFix_Solid().SolidFromShell(shell)
        result=CadShape(solid,{"BLADE_"+name.upper():[sewing.Modified(face) if sewing.IsModified(face) else face] for name,face in faces.items()},
            {"master_deviation_mm":deviations,"surface_grid_counts":counts,"cad_surface_tolerance_mm":tolerance_mm,"cap_methods":cap_methods})
        result.labels["BLADE_HUB_CAP"]=[sewing.Modified(caps[0]) if sewing.IsModified(caps[0]) else caps[0]]
        result.labels["BLADE_TIP_CAP"]=[sewing.Modified(caps[1]) if sewing.IsModified(caps[1]) else caps[1]]
        metrics=self.validate_solid(result)
        if metrics["max_edge_tolerance_mm"]>tolerance_mm:
            raise SurfaceConstructionError(f"Blade cap/edge tolerance {metrics['max_edge_tolerance_mm']:g} exceeds {tolerance_mm:g} mm.")
        return result

    def validate_solid(self,model):
        shape=model.shape;solids=shapes(shape,TopAbs_SOLID)
        valid=BRepCheck_Analyzer(shape).IsValid()
        intersection_check=BRepAlgoAPI_Check(shape,False,True).IsValid()
        props=GProp_GProps()
        volume_error=BRepGProp.VolumePropertiesGK_s(shape,props,1e-9,True,True)
        if not np.isfinite(volume_error) or volume_error<0 or volume_error>1e-5:
            raise InvalidSolidError(f"CAD volume integration did not converge: relative error estimate {volume_error:g}.")
        area=GProp_GProps();BRepGProp.SurfaceProperties_s(shape,area)
        box=Bnd_Box();BRepBndLib.AddOptimal_s(shape,box,False,False)
        bounds=[box.CornerMin().X(),box.CornerMin().Y(),box.CornerMin().Z(),box.CornerMax().X(),box.CornerMax().Y(),box.CornerMax().Z()]
        edge_tolerance=max((BRep_Tool.Tolerance_s(TopoDS.Edge(edge)) for edge in shapes(shape,TopAbs_EDGE)),default=0.)
        closed=all(BRep_Tool.IsClosed_s(TopoDS.Shell(shell)) for shell in shapes(shape,TopAbs_SHELL))
        if not valid or not intersection_check or not closed or not solids or props.Mass()<=0:
            raise InvalidSolidError(f"Invalid CAD: BREP={valid}, self-intersection-free={intersection_check}, closed={closed}, solids={len(solids)}, volume={props.Mass():g}")
        return {"brep_valid":valid,"self_intersection_free":intersection_check,"closed_shell":closed,
            "face_orientation":"PASS (closed shell analyzer and positive volume)","max_edge_tolerance_mm":edge_tolerance,
            "solid_count":len(solids),"volume_mm3":props.Mass(),"volume_integration":"Gauss-Kronrod, B-spline spans, requested relative error 1e-9",
            "volume_relative_error_estimate":volume_error,"surface_area_mm2":area.Mass(),"bbox_mm":bounds}

    def export_step(self,model,path):
        Interface_Static.SetCVal_s("write.step.unit","MM")
        writer=STEPControl_Writer()
        if writer.Transfer(model.shape,STEPControl_AsIs)!=IFSelect_RetDone or writer.Write(str(path))!=IFSelect_RetDone:
            raise CadExportError("STEP writer failed.")

    def read_step(self,path):
        reader=STEPControl_Reader()
        if reader.ReadFile(str(path))!=IFSelect_RetDone or reader.TransferRoots()<1:raise CadExportError("STEP reader failed.")
        return CadShape(reader.OneShape())

    def create_hub_solid(self,flow_segments,backside_segments,bore_radius_mm):
        from OCP.GC import GC_MakeArcOfCircle
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
        def edge(points):
            p=[gp_Pnt(float(r),0.,float(z)) for z,r in points]
            return BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(*p).Value()).Edge() if len(p)==3 else BRepBuilderAPI_MakeEdge(*p).Edge()
        if not flow_segments or not backside_segments or bore_radius_mm is None:
            raise InvalidSolidError("Disk backside and bore radius are required; no dimensions are inferred.")
        start=np.asarray(flow_segments[0][0]);end=np.asarray(flow_segments[-1][-1])
        back_start=np.asarray(backside_segments[0][0]);back_end=np.asarray(backside_segments[-1][-1])
        if bore_radius_mm<0 or abs(back_end[1]-bore_radius_mm)>1e-7 or min(point[1] for segment in flow_segments for point in segment)<bore_radius_mm:
            raise InvalidSolidError("Disk backside must end at the specified bore radius, inside the hub flow surface.")
        flow_edges=[edge(segment) for segment in flow_segments];edges=list(flow_edges)
        for a,b in ((end,back_start),):
            if np.linalg.norm(a-b)>1e-10:edges.append(edge([a,b]))
        edges.extend(edge(segment) for segment in backside_segments)
        bore_front=np.array([start[0],bore_radius_mm])
        for a,b in ((back_end,bore_front),(bore_front,start)):
            if np.linalg.norm(a-b)>1e-10:edges.append(edge([a,b]))
        wire=BRepBuilderAPI_MakeWire()
        for e in edges:wire.Add(e)
        if not wire.IsDone():raise InvalidSolidError("Disk R/Z section is not a connected wire.")
        face=BRepBuilderAPI_MakeFace(wire.Wire(),True)
        if not face.IsDone():raise InvalidSolidError("Disk closed R/Z face failed.")
        revolve=BRepPrimAPI_MakeRevol(face.Face(),gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)),True)
        if not revolve.IsDone():raise InvalidSolidError("Disk revolution failed.")
        labels=self._revolved_roles(revolve,wire.Wire(),{"HUB_FLOW_SURFACE":flow_edges})
        model=CadShape(revolve.Shape(),labels)
        self.validate_solid(model);return model

    @staticmethod
    def _history_labels(builder,labels):
        result={};actual=shapes(builder.Shape(),TopAbs_FACE)
        for name,originals in labels.items():
            result[name]=[]
            for face in originals:
                modified=list(builder.Modified(face))
                candidates=modified if modified else ([] if builder.IsDeleted(face) else [face])
                result[name].extend(candidate for candidate in candidates if any(candidate.IsSame(present) for present in actual))
        return result

    def boolean_union(self,blade,hub):
        try:
            fuse=BRepAlgoAPI_Fuse(hub.shape,blade.shape);fuse.Build()
            if not fuse.IsDone():raise BooleanUnionError("OCCT fuse failed.")
            labels=self._history_labels(fuse,{key:hub.labels.get(key,[])+blade.labels.get(key,[]) for key in hub.labels.keys()|blade.labels.keys()})
            model=CadShape(fuse.Shape(),labels)
            metrics=self.validate_solid(model)
            if metrics["solid_count"]!=1:raise BooleanUnionError("Blade and disk do not form one connected solid.")
            return model
        except BooleanUnionError:raise
        except Exception as exc:raise BooleanUnionError(str(exc)) from exc

    def root_edges(self,model):
        face_edges=[(face,shapes(face,TopAbs_EDGE)) for face in shapes(model.shape,TopAbs_FACE)]
        tagged=lambda face,label:any(face.IsSame(other) for other in model.labels.get(label,[]))
        roots=[];roles=set();model.root_edge_tags=[]
        for edge in shapes(model.shape,TopAbs_EDGE):
            if any(edge.IsSame(old) for old in roots):continue
            adjacent=[face for face,edges in face_edges if any(edge.IsSame(other) for other in edges)]
            if not any(tagged(face,"HUB_FLOW_SURFACE") for face in adjacent):continue
            names={name for name in ("BLADE_PS","BLADE_SS","BLADE_LE","BLADE_TE") if any(tagged(face,name) for face in adjacent)}
            if len(names)>1:raise FilletGenerationError("Ambiguous blade/root face adjacency; no arbitrary edge selection.")
            if names:
                roots.append(edge);roles.update(names);model.root_edge_tags.append((edge,"HUB_FILLET_"+next(iter(names))[6:]))
        if roles!={"BLADE_PS","BLADE_SS","BLADE_LE","BLADE_TE"}:
            raise FilletGenerationError("Root edge identification incomplete: "+str(sorted(roles)))
        return roots

    def apply_fillet(self,model,root_edges,radius_mm):
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
        if not root_edges or not np.isfinite(radius_mm) or radius_mm<=0:raise FilletGenerationError("A positive radius and unambiguous root edges are required.")
        try:
            builder=BRepFilletAPI_MakeFillet(model.shape)
            for edge in root_edges:builder.Add(float(radius_mm),TopoDS.Edge(edge))
            builder.Build()
            if not builder.IsDone():raise FilletGenerationError(f"OCCT root fillet R{radius_mm:g} failed; radius was not reduced.")
            fillet_faces=[]
            for edge in root_edges:
                for face in builder.Generated(edge):
                    if face.ShapeType()==TopAbs_FACE and not any(face.IsSame(old) for old in fillet_faces):fillet_faces.append(face)
            if not fillet_faces:raise FilletGenerationError("Kernel returned no generated root fillet faces.")
            labels=self._history_labels(builder,model.labels);labels["HUB_FILLET"]=fillet_faces
            for edge,role in model.root_edge_tags:
                labels.setdefault(role,[]).extend(face for face in builder.Generated(edge) if face.ShapeType()==TopAbs_FACE)
            result=CadShape(builder.Shape(),labels,{"fillet_radius_mm":float(radius_mm),"root_edge_count":len(root_edges),"fillet_face_count":len(fillet_faces)})
            self.validate_solid(result)
            return result
        except FilletGenerationError:raise
        except Exception as exc:raise FilletGenerationError(f"R{radius_mm:g}: {exc}") from exc

    def rotate(self,model,angle_rad):
        transform=gp_Trsf();transform.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)),float(angle_rad))
        builder=BRepBuilderAPI_Transform(model.shape,transform,True)
        labels={name:[builder.ModifiedShape(face) for face in faces] for name,faces in model.labels.items()}
        return CadShape(builder.Shape(),labels,dict(model.metrics))

    def subtract(self,a,b):
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
        builder=BRepAlgoAPI_Cut(a.shape,b.shape);builder.Build()
        if not builder.IsDone():raise BooleanUnionError("CAD subtraction failed.")
        labels=self._history_labels(builder,{key:a.labels.get(key,[])+b.labels.get(key,[]) for key in a.labels.keys()|b.labels.keys()})
        return CadShape(builder.Shape(),labels)

    def check_pair_interference(self,a,b,tolerance):
        common=BRepAlgoAPI_Common(a.shape,b.shape);common.Build()
        if not common.IsDone():raise InvalidSolidError("Blade/splitter interference calculation failed.")
        props=GProp_GProps();BRepGProp.VolumeProperties_s(common.Shape(),props,1e-9,True,False)
        overlap=props.Mass()
        if overlap>max(tolerance**3,1e-8):raise InvalidSolidError(f"Blade/splitter interference: overlap {overlap:g} mm3.")
        return overlap

    def check_interference(self,feature,blade_count,tolerance):
        if type(blade_count) is not int or blade_count<1:raise InvalidSolidError("Invalid blade count.")
        maximum=0.
        for i in range(1,blade_count//2+1):
            other=self.rotate(feature,2*np.pi*i/blade_count)
            common=BRepAlgoAPI_Common(feature.shape,other.shape);common.Build()
            if not common.IsDone():raise InvalidSolidError("Inter-blade interference calculation failed.")
            props=GProp_GProps();BRepGProp.VolumeProperties_s(common.Shape(),props,1e-9,True,False)
            maximum=max(maximum,props.Mass())
            if props.Mass()>max(tolerance**3,1e-8):raise InvalidSolidError(f"Inter-blade interference at pitch {i}: overlap {props.Mass():g} mm3.")
        return {"inter_blade_interference":"PASS","max_overlap_volume_mm3":maximum,"copies_checked":blade_count//2}

    def full_impeller(self,single,hub,blade_count,tolerance,check_interference=True):
        from OCP.collections import List_TopoDS_Shape
        feature=self.subtract(single,hub)
        interference=self.check_interference(feature,blade_count,tolerance) if check_interference else {}
        if blade_count==1:return single
        copies=[self.rotate(feature,2*np.pi*i/blade_count) for i in range(1,blade_count)]
        arguments=List_TopoDS_Shape();arguments.Append(single.shape)
        tools=List_TopoDS_Shape()
        for model in copies:tools.Append(model.shape)
        fuse=BRepAlgoAPI_Fuse();fuse.SetArguments(arguments);fuse.SetTools(tools);fuse.SetRunParallel(True);fuse.Build()
        if not fuse.IsDone():raise BooleanUnionError("Full impeller batch fuse failed.")
        inputs=[single,*copies];keys=set().union(*(m.labels for m in inputs))
        labels=self._history_labels(fuse,{key:[f for m in inputs for f in m.labels.get(key,[])] for key in keys})
        result=CadShape(fuse.Shape(),labels,interference)
        if self.validate_solid(result)["solid_count"]!=1:raise BooleanUnionError("Full impeller is not one connected solid.")
        return result

    def sector(self,model,blade_count):
        from OCP.gp import gp_Ax2
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        if blade_count==1:return model
        metrics=self.validate_solid(model);x0,y0,z0,x1,y1,z1=metrics["bbox_mm"]
        radius=2*max(abs(x0),abs(x1),abs(y0),abs(y1));margin=max(radius*.01,1.)
        wedge=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0,0,z0-margin),gp_Dir(0,0,1)),radius,z1-z0+2*margin,2*np.pi/blade_count).Shape()
        common=BRepAlgoAPI_Common(model.shape,wedge);common.Build()
        if not common.IsDone():raise BooleanUnionError("Periodic-sector intersection failed.")
        result=CadShape(common.Shape(),self._history_labels(common,model.labels),dict(model.metrics))
        self.validate_solid(result)
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane
        result.labels.update(PERIODIC_LOW=[],PERIODIC_HIGH=[])
        for face in shapes(result.shape,TopAbs_FACE):
            adaptor=BRepAdaptor_Surface(TopoDS.Face(face))
            if adaptor.GetType()!=GeomAbs_Plane:continue
            plane=adaptor.Plane();normal=plane.Axis().Direction()
            if abs(normal.Z())>1e-8 or plane.Distance(gp_Pnt(0,0,0))>1e-7:continue
            props=GProp_GProps();BRepGProp.SurfaceProperties_s(face,props)
            point=props.CentreOfMass();angle=np.arctan2(point.Y(),point.X())
            for label,target in (("PERIODIC_LOW",0.),("PERIODIC_HIGH",2*np.pi/blade_count)):
                if abs(np.arctan2(np.sin(angle-target),np.cos(angle-target)))<1e-7:result.labels[label].append(face)
        return result

    def create_flow_passage(self,hub_segments,shroud_segments):
        from OCP.GC import GC_MakeArcOfCircle
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
        def edge(points):
            pts=[gp_Pnt(float(r),0.,float(z)) for z,r in points]
            return BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(*pts).Value()).Edge() if len(pts)==3 else BRepBuilderAPI_MakeEdge(*pts).Edge()
        grouped={"HUB":[edge(s) for s in hub_segments],"SHROUD":[edge(list(reversed(s))) for s in reversed(shroud_segments)],
                 "OUTLET":[edge([hub_segments[-1][-1],shroud_segments[-1][-1]])],
                 "INLET":[edge([shroud_segments[0][0],hub_segments[0][0]])]}
        wire=BRepBuilderAPI_MakeWire()
        for name in ("HUB","OUTLET","SHROUD","INLET"):
            for e in grouped[name]:wire.Add(e)
        if not wire.IsDone():raise InvalidSolidError("Flow passage boundary is not connected.")
        face=BRepBuilderAPI_MakeFace(wire.Wire(),True)
        if not face.IsDone():raise InvalidSolidError("Flow passage R/Z face failed.")
        revolve=BRepPrimAPI_MakeRevol(face.Face(),gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)),True)
        if not revolve.IsDone():raise InvalidSolidError("Flow passage revolution failed.")
        result=CadShape(revolve.Shape(),self._revolved_roles(revolve,wire.Wire(),grouped))
        self.validate_solid(result);return result

    def triangulate(self,model,tolerance=.2):
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.TopLoc import TopLoc_Location
        BRepMesh_IncrementalMesh(model.shape,float(tolerance),False,.3,True)
        result={}
        for face in shapes(model.shape,TopAbs_FACE):
            face=TopoDS.Face(face);location=TopLoc_Location();mesh=BRep_Tool.Triangulation_s(face,location)
            if mesh is None:continue
            tags=[name for name,faces in model.labels.items() if any(face.IsSame(other) for other in faces)]
            label="HUB_FILLET" if "HUB_FILLET" in tags else next((t for t in tags if t.startswith("BLADE_")),"HUB_DISK")
            triangles=result.setdefault(label,[])
            for i in range(1,mesh.NbTriangles()+1):
                tri=mesh.Triangle(i);vertices=[]
                for j in (1,2,3):
                    point=mesh.Node(tri.Value(j)).Transformed(location.Transformation())
                    vertices.append([point.X(),point.Y(),point.Z()])
                triangles.append(vertices)
        return result

    def _join_tangents(self,sections):
        from ..geometry.cad_surface_reference import join_surface_tangents
        return join_surface_tangents(sections)

    def edge_polylines(self,model):
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        result=[]
        for edge in shapes(model.shape,TopAbs_EDGE):
            curve=BRepAdaptor_Curve(TopoDS.Edge(edge));a,b=curve.FirstParameter(),curve.LastParameter()
            if not np.isfinite([a,b]).all():continue
            row=[]
            for t in np.linspace(a,b,41):
                point=curve.Value(float(t));row.append([point.X(),point.Y(),point.Z()])
            result.append(row)
        return result

    @staticmethod
    def _revolved_roles(revolve,wire,groups):
        # MakeWire can replace vertices/edges while connecting the chain. Match
        # canonical edges geometrically before querying the revolution history.
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        def signature(edge):
            curve=BRepAdaptor_Curve(TopoDS.Edge(edge));a,b=curve.FirstParameter(),curve.LastParameter()
            return np.array([[p.X(),p.Y(),p.Z()] for p in (curve.Value(a),curve.Value((a+b)/2),curve.Value(b))])
        canonical=[(edge,signature(edge)) for edge in shapes(wire,TopAbs_EDGE)]
        result={}
        for name,originals in groups.items():
            result[name]=[]
            for original in originals:
                points=signature(original)
                matches=[edge for edge,other in canonical if min(np.max(np.linalg.norm(points-other,axis=1)),np.max(np.linalg.norm(points-other[::-1],axis=1)))<=1e-6]
                if len(matches)!=1:raise InvalidSolidError("Ambiguous revolved surface role: "+name)
                for face in revolve.Generated(matches[0]):
                    if not any(face.IsSame(old) for old in result[name]):result[name].append(face)
        return result

    def surface_roles(self,model):
        result={};actual=shapes(model.shape,TopAbs_FACE)
        for name,faces in model.labels.items():
            result[name]=[]
            for face in faces:
                if not any(face.IsSame(present) for present in actual):continue
                props=GProp_GProps();BRepGProp.SurfaceProperties_s(face,props)
                point=props.CentreOfMass();box=Bnd_Box();BRepBndLib.AddOptimal_s(face,box,False,False)
                result[name].append({"area_mm2":props.Mass(),"centroid_mm":[point.X(),point.Y(),point.Z()],
                    "bbox_mm":[box.CornerMin().X(),box.CornerMin().Y(),box.CornerMin().Z(),box.CornerMax().X(),box.CornerMax().Y(),box.CornerMax().Z()]})
        return {name:values for name,values in result.items() if values}
