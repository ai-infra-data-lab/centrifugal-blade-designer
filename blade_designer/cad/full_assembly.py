"""Construct a filleted full wheel without cutting tangent blends off its Hub."""
from numbers import Real
import numpy as np
from .errors import BooleanUnionError,FilletGenerationError,InvalidSolidError


def build_filleted_full_impeller(backend,blades,hub,blade_count,radius,tolerance):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRep import BRep_Tool
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_SOLID,TopAbs_SHELL
    from OCP.TopoDS import TopoDS
    from OCP.collections import List_TopoDS_Shape
    from .occt_backend import CadShape,shapes
    from .cad_validation import fillet_samples,require_fillet_samples

    if type(blade_count) is not int or blade_count<1:raise BooleanUnionError('Invalid full-wheel blade count.')
    if any(not isinstance(v,Real) or isinstance(v,bool) or not np.isfinite(v) or v<=0 for v in (radius,tolerance)):
        raise BooleanUnionError('Positive finite radius and CAD tolerance are required.')
    blades=list(blades)
    if not blades or any(not isinstance(pair,(tuple,list)) or len(pair)!=2 for pair in blades):
        raise BooleanUnionError('Named construction blades are required.')
    names=[pair[0] for pair in blades]
    if any(not isinstance(name,str) or not name for name in names) or len(set(names))!=len(names):
        raise BooleanUnionError('Construction blade names must be unique nonempty strings.')

    inputs=[hub];expected={}
    for index in range(blade_count):
        for name,source in blades:
            # Keep the single-passage preview's labels and shape untouched.
            model=backend.rotate(source,2*np.pi*index/blade_count) if index else CadShape(
                source.shape,{key:list(value) for key,value in source.labels.items()},dict(source.metrics))
            if not backend.check_buried_root_caps(model,hub):
                raise BooleanUnionError('Full filleted construction requires a buried root continuation.')
            model.labels={key:value for key,value in model.labels.items() if not key.startswith('BLADE_GROUP_')}
            group=name+'@'+str(index)
            model.labels['BLADE_GROUP_'+group]=[face for role in ('LE','PS','TE','SS','TIP_CAP')
                for face in model.labels.get('BLADE_'+role,[])]
            expected[group]={'blade':name,'pitch_index':index,
                'cap_count':len(model.labels['BLADE_HUB_CAP']),'cap_containment':'PASS'}
            inputs.append(model)

    arguments=List_TopoDS_Shape();arguments.Append(hub.shape);tools=List_TopoDS_Shape()
    for model in inputs[1:]:tools.Append(model.shape)
    builder=BRepAlgoAPI_Fuse();builder.SetArguments(arguments);builder.SetTools(tools)
    builder.SetRunParallel(True);builder.SetNonDestructive(True);builder.Build()
    if not builder.IsDone():raise BooleanUnionError('Raw full-wheel union failed; no fillet or output accepted.')
    keys=set().union(*(model.labels for model in inputs))
    labels=backend._history_labels(builder,{key:[face for model in inputs for face in model.labels.get(key,[])] for key in keys})
    raw=CadShape(builder.Shape(),labels)
    if (not BRepCheck_Analyzer(raw.shape).IsValid() or len(shapes(raw.shape,TopAbs_SOLID))!=1 or
            not all(BRep_Tool.IsClosed_s(TopoDS.Shell(shell)) for shell in shapes(raw.shape,TopAbs_SHELL))):
        raise BooleanUnionError('Raw full-wheel union is not one closed valid construction solid.')
    if raw.labels.get('BLADE_HUB_CAP'):raise BooleanUnionError('Construction root cap survived full-wheel union.')
    props=GProp_GProps();error=BRepGProp.VolumePropertiesGK_s(raw.shape,props,1e-9,True,True)
    if not np.isfinite(error) or not 0<=error<=1e-5 or not np.isfinite(props.Mass()) or props.Mass()<=0:
        raise BooleanUnionError('Raw full-wheel construction volume did not converge.')

    roots=backend.root_edges(raw);coverage={group:set() for group in expected}
    for edge,role,group in raw.root_edge_tags:
        if group not in coverage:raise FilletGenerationError('Unexpected full-wheel root owner.')
        coverage[group].add(role.removeprefix('HUB_FILLET_'))
    if any(roles!={'LE','PS','TE','SS'} for roles in coverage.values()):
        raise FilletGenerationError('Each blade instance requires LE/TE/PS/SS root coverage.')
    for group,roles in coverage.items():expected[group]['root_roles']=sorted(roles)

    # Construction self-intersection is not reported as PASS. The finished
    # fillet solid must pass the complete native check in apply_fillet below.
    rounded=backend.apply_fillet(raw,roots,radius)
    if set(rounded.metrics.get('fillet_groups',{}))!=set(expected):
        raise FilletGenerationError('Incomplete full-wheel fillet group ownership.')
    measurement=fillet_samples(rounded,radius);require_fillet_samples(measurement)
    separation=backend.check_root_group_separation(rounded,tolerance,use_bounds=True,include_original_pairs=True)
    actual=backend.validate_solid(rounded)
    if (actual['solid_count']!=1 or not np.isfinite(actual['max_edge_tolerance_mm']) or
            actual['max_edge_tolerance_mm']>tolerance):
        raise InvalidSolidError('Finished full wheel exceeds the requested topology or CAD tolerance.')
    rounded.metrics.update(full_assembly_method='raw_full_union_then_single_fillet',
        periodic_root_coverage=expected,full_root_group_separation=separation,
        full_fillet_radius_measurements=measurement,raw_full_construction={
            'brep_valid':True,'closed_shell':True,'solid_count':1,'volume_mm3':props.Mass(),
            'volume_relative_error_estimate':error,'self_intersection_free':'NOT_TESTED_INTERMEDIATE'})
    return rounded
