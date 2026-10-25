"""Mechanical one-pitch cut with a shared, rotated pair of non-planar faces."""
import numpy as np
from scipy.interpolate import RectBivariateSpline
from .errors import InvalidSolidError


def _compound(items):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    result=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(result)
    for item in items:builder.Add(result,item)
    return result


def _tool(backend,phase,bbox,tolerance):
    from OCP.Geom import Geom_BSplineSurface
    from OCP.collections import Array2_gp_Pnt,Array1_double,Array1_int
    from OCP.gp import gp_Pnt
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace,BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeSolid
    from OCP.BRepFill import BRepFill
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.TopoDS import TopoDS
    from OCP.TopAbs import TopAbs_EDGE,TopAbs_SHELL
    from .occt_backend import CadShape,shapes
    radius=np.hypot(max(abs(bbox[0]),abs(bbox[3])),max(abs(bbox[1]),abs(bbox[4])))
    margin=max(1.,radius*.05)
    outer=(radius+margin)/np.cos(phase.pitch/2)
    # Extra stations inside the blade rectangle keep the far-field extension
    # from consuming the entire interpolation resolution.
    rs=np.unique(np.r_[np.linspace(0,outer,25),np.linspace(phase.origin[0],phase.origin[0]+phase.scale[0]*phase.upper[0],33)])
    zs=np.unique(np.r_[np.linspace(bbox[2]-margin,bbox[5]+margin,17),
                        np.linspace(phase.origin[1],phase.origin[1]+phase.scale[1]*phase.upper[1],33)])
    rr,zz=np.meshgrid(rs,zs,indexing='ij')
    angle=phase(np.column_stack((rr.ravel(),zz.ravel()))).reshape(rr.shape)
    xyz=np.stack((rr*np.cos(angle),rr*np.sin(angle),zz),axis=-1)
    splines=[RectBivariateSpline(rs,zs,xyz[:,:,i],s=0) for i in range(3)]
    poles=np.stack([s.get_coeffs().reshape(len(rs),len(zs)) for s in splines],axis=-1)
    grid=Array2_gp_Pnt(1,len(rs),1,len(zs))
    for i in range(len(rs)):
        for j in range(len(zs)):grid.SetValue(i+1,j+1,gp_Pnt(*map(float,poles[i,j])))
    def knots(values):
        unique,counts=np.unique(values,return_counts=True)
        k=Array1_double(1,len(unique));m=Array1_int(1,len(unique))
        for i,(v,n) in enumerate(zip(unique,counts),1):k.SetValue(i,float(v));m.SetValue(i,int(n))
        return k,m
    uk,um=knots(splines[0].get_knots()[0]);vk,vm=knots(splines[0].get_knots()[1])
    surface=Geom_BSplineSurface(grid,uk,vk,um,vm,3,3)
    low=BRepBuilderAPI_MakeFace(surface,tolerance*.01).Face()
    high=backend.rotate(CadShape(low),phase.pitch).shape
    sewing=BRepBuilderAPI_Sewing(tolerance*.01)
    sewing.Add(low);sewing.Add(high)
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    for edge in shapes(low,TopAbs_EDGE):
        curve=BRepAdaptor_Curve(TopoDS.Edge(edge))
        points=[curve.Value(float(t)) for t in np.linspace(curve.FirstParameter(),curve.LastParameter(),5)]
        if max(np.hypot(p.X(),p.Y()) for p in points)<1e-7:continue  # common rotation axis
        other=backend.rotate(CadShape(edge),phase.pitch).shape
        sewing.Add(BRepFill.Face_s(TopoDS.Edge(edge),TopoDS.Edge(other)))
    sewing.Perform();shells=shapes(sewing.SewedShape(),TopAbs_SHELL)
    if len(shells)!=1:raise InvalidSolidError('Periodic cutting tool is not one shell.')
    solid=BRepBuilderAPI_MakeSolid(TopoDS.Shell(shells[0])).Solid()
    fixer=ShapeFix_Solid(solid);fixer.Perform();solid=fixer.Solid()
    tool=CadShape(solid)
    metrics=backend.validate_solid(tool)
    if metrics['solid_count']!=1 or metrics['max_edge_tolerance_mm']>tolerance:
        raise InvalidSolidError('Periodic cutting tool exceeds topology/tolerance limits.')
    # Sewing may replace faces. Match the unchanged supporting surface rather
    # than assuming face indices or a planar normal.
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_FACE
    labels={}
    for name,original in (('PERIODIC_LOW',low),('PERIODIC_HIGH',high)):
        source=BRep_Tool.Surface_s(TopoDS.Face(original))
        labels[name]=[face for face in shapes(solid,TopAbs_FACE) if BRep_Tool.Surface_s(TopoDS.Face(face)) is source]
        if len(labels[name])!=1:raise InvalidSolidError('Ambiguous periodic tool surface ownership.')
    return tool,labels


def cut_following_sector(backend,full,groups,blade_count,tolerance,progress=None):
    """Cut a natively validated private copy; never modify the caller's BREP."""
    from copy import deepcopy
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from .occt_backend import CadShape
    fingerprint=backend._solid_fingerprint(full.shape)
    copier=BRepBuilderAPI_Copy(full.shape,True,True)
    if not copier.IsDone():raise InvalidSolidError('Cannot obtain a private BREP for the periodic cut.')
    private=CadShape(copier.Shape(),{name:[copier.ModifiedShape(face) for face in faces]
                                  for name,faces in full.labels.items()},deepcopy(full.metrics))
    try:
        if progress is not None:progress('FOLLOWING SECTOR / PRIVATE FULL VALIDITY')
        source_metrics=backend.validate_solid(private)
        result=_cut_private_sector(backend,private,list(groups),blade_count,tolerance,source_metrics,progress)
        result.metrics['following_sector']['source_copy']='KERNEL_COPY_NATIVE_VALIDATED'
        result.metrics['following_sector']['source_fingerprint_unchanged']=True
        return result
    finally:
        if backend._solid_fingerprint(full.shape)!=fingerprint:
            raise InvalidSolidError('Periodic cutting modified the source BREP; output rejected.')


def _cut_private_sector(backend,full,groups,blade_count,tolerance,source_metrics,progress):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopAbs import TopAbs_FACE
    from .occt_backend import CadShape,shapes
    from ..geometry.sector_boundary import blade_following_phase
    from .boundary_samples import compare_boundary_samples,require_boundary_samples
    def notify(stage):
        if progress is not None:progress('FOLLOWING SECTOR / '+stage)
    notify('TOOL')
    phase=blade_following_phase(groups,blade_count)
    # The private full copy, actual output and reconstruction each receive
    # complete native checks; no validation is borrowed across wrappers.
    before=source_metrics
    tool,tool_labels=_tool(backend,phase,before['bbox_mm'],tolerance)
    protected=[]
    owners=[key for key in full.labels if key.startswith('BLADE_GROUP_')]
    if not owners:raise InvalidSolidError('Per-blade ownership is required for a following sector.')
    for name,faces in full.labels.items():
        if name.startswith('BLADE_GROUP_') or name=='HUB_FILLET':
            for face in faces:
                if not any(face.IsSame(old) for old in protected):protected.append(face)
    if not protected:raise InvalidSolidError('No completed blade/fillet surfaces to protect.')
    distances={}
    for label,faces in tool_labels.items():
        notify('BLADE / FILLET CLEARANCE '+label)
        distance=BRepExtrema_DistShapeShape(_compound(faces),_compound(protected));distance.Perform()
        if not distance.IsDone() or not np.isfinite(distance.Value()) or distance.Value()<=tolerance:
            raise InvalidSolidError('Following boundary intersects or approaches a blade/root fillet: '+label)
        distances[label]=float(distance.Value())
    notify('CUT')
    common=BRepAlgoAPI_Common(full.shape,tool.shape)
    common.SetRunParallel(True);common.SetNonDestructive(True);common.Build()
    if not common.IsDone():raise InvalidSolidError('Following-sector Boolean intersection failed.')
    labels=backend._history_labels(common,{**full.labels,**tool_labels})
    actual=shapes(common.Shape(),TopAbs_FACE)
    retained=[]
    for owner in owners:
        faces=full.labels[owner]
        present=[face for face in faces if any(face.IsSame(p) for p in actual)]
        if present:
            if len(present)!=len(faces):raise InvalidSolidError('A blade was partially cut: '+owner)
            retained.append(owner.removeprefix('BLADE_GROUP_'))
        elif labels.get(owner):raise InvalidSolidError('A blade surface was modified by the periodic cut.')
    expected={name+'@0' for name,_ in groups}
    if set(retained)!=expected:raise InvalidSolidError('Following sector did not retain exactly the selected main/splitter set: '+str(retained))
    for name,faces in full.labels.items():
        if name.startswith('HUB_FILLET_GROUP_'):
            group=name.removeprefix('HUB_FILLET_GROUP_')
            for face in faces:
                present=any(face.IsSame(p) for p in actual)
                if present!=(group in expected):
                    raise InvalidSolidError('Root fillet ownership/completeness changed by the cut: '+group)
    result=CadShape(common.Shape(),labels,dict(full.metrics))
    notify('SECTOR VALIDITY')
    checked=backend.validate_solid(result)
    if checked['solid_count']!=1 or checked['max_edge_tolerance_mm']>tolerance:
        raise InvalidSolidError('Following sector must be one closed solid within CAD tolerance.')
    for label in tool_labels:
        if not labels.get(label):raise InvalidSolidError('Missing following periodic boundary: '+label)
    low=backend.rotate(CadShape(_compound(labels['PERIODIC_LOW'])),phase.pitch)
    high=CadShape(_compound([face.Reversed() for face in labels['PERIODIC_HIGH']]))
    notify('PERIODIC SURFACE SAMPLES')
    match=compare_boundary_samples(low,high,tolerance)
    require_boundary_samples(match)
    budget=max(before['volume_mm3']*1e-7,before['surface_area_mm2']*max(1e-7,tolerance*.01))
    error=abs(checked['volume_mm3']*blade_count-before['volume_mm3'])
    if error>budget:raise InvalidSolidError('Following-sector volume does not reproduce the full wheel.')
    # A volume ratio alone cannot exclude compensating geometric errors.
    # Rebuild all sectors and compare every boundary face in both directions.
    # Boolean subtraction of nearly coincident full wheels is ill-conditioned;
    # sampled correspondence is explicitly not a global material certificate.
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.collections import List_TopoDS_Shape
    arguments=List_TopoDS_Shape();arguments.Append(result.shape)
    tools=List_TopoDS_Shape()
    for i in range(1,blade_count):tools.Append(backend.rotate(result,i*phase.pitch).shape)
    notify('RECONSTRUCT FULL WHEEL')
    union=BRepAlgoAPI_Fuse();union.SetArguments(arguments);union.SetTools(tools)
    union.SetRunParallel(True);union.SetNonDestructive(True);union.Build()
    if not union.IsDone():raise InvalidSolidError('Rotated following sectors could not be reconstructed.')
    notify('RECONSTRUCTED VALIDITY')
    rebuilt=CadShape(union.Shape());reconstruction=backend.validate_solid(rebuilt)
    if reconstruction['solid_count']!=1 or reconstruction['max_edge_tolerance_mm']>tolerance:
        raise InvalidSolidError('Reconstructed wheel exceeds topology/tolerance limits.')
    notify('RECONSTRUCTED BOUNDARY SAMPLES')
    correspondence=compare_boundary_samples(full,rebuilt,tolerance)
    require_boundary_samples(correspondence)
    overlap=checked['volume_mm3']*blade_count-reconstruction['volume_mm3']
    if not np.isfinite(overlap) or abs(overlap)>budget:
        raise InvalidSolidError('Rotated following sectors overlap or lose material.')
    result.metrics['following_sector']={'status':'PASS','method':'rz_phase_bspline_rotated_pair',
        'pitch_rad':phase.pitch,'retained_groups':sorted(expected),'blade_and_fillet_faces_unchanged':True,
        'boundary_clearance_mm':distances,'periodic_surface_samples':match,
        'full_volume_difference_mm3':error,'full_volume_budget_mm3':budget,
        'reconstruction':{'status':'PASS_SAMPLED_VOLUME_BUDGET','boundary_samples':correspondence,
            'overlap_volume_mm3':overlap,'global_material_coverage':'NOT_CONFIRMED',
            'full_body_boolean_difference':'NOT_PERFORMED_NEAR_COINCIDENT_OPERATION'},
        'sample_phase_margin_rad':phase.sample_margin_rad,'ansys_import':'NOT_TESTED','ansys_mesh':'NOT_TESTED'}
    return result
