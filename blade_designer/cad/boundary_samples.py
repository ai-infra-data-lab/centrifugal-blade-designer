"""Classified samples on every BREP face; not a global surface certificate."""
import math
import numpy as np
from .errors import CadExportError
from .cad_validation import trimmed_face_parameters,_finite_number


def _point_normal(face,u,v):
    from OCP.BRep import BRep_Tool
    from OCP.GeomLProp import GeomLProp_SLProps
    from OCP.TopAbs import TopAbs_FORWARD,TopAbs_REVERSED
    surface=BRep_Tool.Surface_s(face);point=surface.Value(u,v)
    props=GeomLProp_SLProps(surface,u,v,1,1e-9)
    if not props.IsNormalDefined():raise CadExportError('Undefined boundary sample normal.')
    orientation=face.Orientation()
    if orientation not in (TopAbs_FORWARD,TopAbs_REVERSED):
        raise CadExportError('Unsupported boundary face orientation.')
    sign=-1 if orientation==TopAbs_REVERSED else 1
    normal=props.Normal();xyz=[point.X(),point.Y(),point.Z()]
    vector=[sign*normal.X(),sign*normal.Y(),sign*normal.Z()]
    if not all(_finite_number(value) for value in xyz+vector):
        raise CadExportError('Non-finite boundary point or normal.')
    return point,vector


def _faces(model):
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from .occt_backend import shapes
    result=[TopoDS.Face(face) for face in shapes(model.shape,TopAbs_FACE)]
    if not result:raise CadExportError('No boundary faces to compare.')
    return result


def _directed(source,target,direction,progress):
    from OCP.BRep import BRep_Tool
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape,BRepExtrema_SupportType
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    bounds=[]
    for face in target:
        box=Bnd_Box();BRepBndLib.AddOptimal_s(face,box,False,True)
        if box.IsVoid():raise CadExportError('Empty target boundary bounds.')
        lo,hi=box.CornerMin(),box.CornerMax()
        bounds.append([lo.X(),lo.Y(),lo.Z(),hi.X(),hi.Y(),hi.Z()])
    bounds=np.asarray(bounds)
    if not np.isfinite(bounds).all() or np.any(bounds[:,:3]>bounds[:,3:]):
        raise CadExportError('Invalid target boundary bounds.')
    records=[];queries=0;reused=0;projected=0
    for index,face in enumerate(source):
        parameters=trimmed_face_parameters(face)
        if not parameters:raise CadExportError(f'{direction}: face {index} has no classified samples.')
        gaps=[];angles=[];matched=set()
        for u,v in parameters:
            point,normal=_point_normal(face,u,v);vertex=BRepBuilderAPI_MakeVertex(point).Vertex()
            position=np.asarray([point.X(),point.Y(),point.Z()])
            with np.errstate(over='ignore',invalid='ignore',under='ignore'):
                gap=np.maximum(0,np.maximum(np.nextafter(bounds[:,:3]-position,-np.inf),
                    np.nextafter(position-bounds[:,3:],-np.inf)))
            lower=np.max(gap,axis=1)
            # An unavailable lower bound cannot prune a face.
            lower=np.where(np.isfinite(lower),lower,0.)
            best=float('inf');candidates=[]
            for target_index in np.argsort(lower,kind='stable'):
                if lower[target_index]>best+1e-9:break
                other=target[target_index];distance=BRepExtrema_DistShapeShape(vertex,other);queries+=1
                if (not distance.IsDone() or distance.NbSolution()<1 or
                        not _finite_number(distance.Value()) or distance.Value()<0):
                    raise CadExportError(f'{direction}: face {index} boundary distance is unavailable.')
                best=min(best,distance.Value())
                for solution in range(1,distance.NbSolution()+1):
                    uv=(distance.ParOnFaceS2(solution) if distance.SupportTypeShape2(solution)==
                        BRepExtrema_SupportType.BRepExtrema_IsInFace else None)
                    candidates.append((distance.Value(),int(target_index),uv,distance.PointOnShape2(solution)))
            if not candidates:raise CadExportError('No target boundary distance evidence.')
            nearest=min(item[0] for item in candidates);normal_angles=[]
            for value,target_index,uv,closest in candidates:
                if value>nearest+1e-9:continue
                other=target[target_index]
                if uv is None:
                    projection=GeomAPI_ProjectPointOnSurf(closest,BRep_Tool.Surface_s(other));projected+=1
                    if not projection.IsDone():raise CadExportError('Target boundary normal parameters unavailable.')
                    uv=projection.LowerDistanceParameters()
                else:reused+=1
                _,opposite=_point_normal(other,*uv)
                cosine=sum(a*b for a,b in zip(normal,opposite))
                if not _finite_number(cosine):raise CadExportError('Non-finite boundary normal comparison.')
                normal_angles.append(math.degrees(math.acos(max(-1.,min(1.,cosine)))))
                matched.add(target_index)
            gaps.append(nearest);angles.append(min(normal_angles))
        records.append({'face_index':index,'sample_count':len(parameters),'max_distance_mm':max(gaps),
            'max_normal_angle_deg':max(angles),'nearest_target_faces':sorted(matched)})
        if progress is not None and ((index+1)%max(1,len(source)//16)==0 or index+1==len(source)):
            progress(direction,index+1,len(source))
    return {'face_count':len(source),'sample_count':sum(row['sample_count'] for row in records),
        'faces':records,'max_distance_mm':max(row['max_distance_mm'] for row in records),
        'max_normal_angle_deg':max(row['max_normal_angle_deg'] for row in records),
        'native_point_face_queries':queries,'normal_uv_reused':reused,'normal_projection_fallbacks':projected}


def compare_boundary_samples(original,imported,tolerance_mm,progress=None):
    if not _finite_number(tolerance_mm) or tolerance_mm<=0:
        raise CadExportError('A positive finite boundary comparison tolerance is required.')
    try:
        first,second=_faces(original),_faces(imported)
        forward=_directed(first,second,'source_to_imported',progress)
        reverse=_directed(second,first,'imported_to_source',progress)
    except CadExportError:raise
    except Exception as exc:raise CadExportError('Boundary sample evaluation failed: '+str(exc)) from exc
    passed=all(row['max_distance_mm']<=tolerance_mm and row['max_normal_angle_deg']<90
        for section in (forward,reverse) for row in section['faces'])
    return {'schema_version':1,'status':'PASS_SAMPLED' if passed else 'FAIL','unit':'mm',
        'requested_tolerance_mm':float(tolerance_mm),'source_to_imported':forward,'imported_to_source':reverse,
        'normal_rule':'Positive oriented-normal dot product at nearest boundary samples; ties within 1e-9 mm.',
        'coverage':'Classified finite samples on every face in both directions.',
        'global_surface_error':'NOT_TESTED','global_normal_alignment':'NOT_TESTED','boundary_role_correspondence':'NOT_TESTED'}


def require_boundary_samples(measurement):
    if not isinstance(measurement,dict) or measurement.get('status')!='PASS_SAMPLED':
        raise CadExportError('STEP boundary distance or normal samples failed; output was not accepted.')
    if (type(measurement.get('schema_version')) is not int or measurement.get('schema_version')!=1 or measurement.get('unit')!='mm' or
            measurement.get('global_surface_error')!='NOT_TESTED' or
            measurement.get('global_normal_alignment')!='NOT_TESTED'):
        raise CadExportError('Invalid boundary evidence scope or unit.')
    tolerance=measurement.get('requested_tolerance_mm')
    if not _finite_number(tolerance) or tolerance<=0:raise CadExportError('Invalid boundary sample tolerance.')
    for direction in ('source_to_imported','imported_to_source'):
        data=measurement.get(direction)
        if not isinstance(data,dict):raise CadExportError('Missing bidirectional boundary evidence.')
        count=data.get('face_count');faces=data.get('faces')
        if type(count) is not int or count<1 or not isinstance(faces,list) or len(faces)!=count:
            raise CadExportError('Incomplete boundary face coverage.')
        if any(not isinstance(row,dict) for row in faces):raise CadExportError('Invalid boundary face evidence.')
        if (any(type(row.get('face_index')) is not int for row in faces) or
                [row.get('face_index') for row in faces]!=list(range(count))):
            raise CadExportError('Missing or duplicate boundary face indices.')
        opposite=measurement.get('imported_to_source' if direction=='source_to_imported' else 'source_to_imported')
        target_count=opposite.get('face_count') if isinstance(opposite,dict) else None
        if type(target_count) is not int or target_count<1:raise CadExportError('Missing target face coverage.')
        for row in faces:
            distance=row.get('max_distance_mm');angle=row.get('max_normal_angle_deg');samples=row.get('sample_count')
            if (type(samples) is not int or samples<1 or not _finite_number(distance) or
                    not 0<=distance<=tolerance or not _finite_number(angle) or not 0<=angle<90):
                raise CadExportError('Boundary samples are missing, non-finite or outside the requested limits.')
            targets=row.get('nearest_target_faces')
            if not isinstance(targets,list) or not targets or any(type(i) is not int or not 0<=i<target_count for i in targets):
                raise CadExportError('Invalid nearest boundary face references.')
        if (type(data.get('sample_count')) is not int or
                data['sample_count']!=sum(row['sample_count'] for row in faces) or
                data.get('max_distance_mm')!=max(row['max_distance_mm'] for row in faces) or
                data.get('max_normal_angle_deg')!=max(row['max_normal_angle_deg'] for row in faces)):
            raise CadExportError('Inconsistent boundary evidence totals.')
