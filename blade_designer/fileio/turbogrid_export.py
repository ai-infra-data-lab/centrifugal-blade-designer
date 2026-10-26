"""TurboGrid ASCII XYZ curves and verified BladeGen initialization syntax.

Sources: Ansys 2026 R1 User Guide 2.1, 10.3.6 and official stator.zip.
LE/TE end keywords are from the 2.1 initialization example, not guessed.
"""
from pathlib import Path
from dataclasses import replace
import os
import numpy as np
from .csv_export import format_number
from ..geometry.meridional_segments import sample_meridional,corner_distances
from ..geometry.geometry_3d import generate_impeller, generate_diffuser_3d
from ..geometry.row_domain import export_wall_intervals
from ..models.parameters import EdgeType

REFERENCE_URL="https://ansyshelp.ansys.com/public/Views/Secured/Doc_Assets/v261/TurboGrid/stator.zip"


def closed_profile(section):
    """Each junction emitted once; only closure repeats the first point."""
    xyz=np.concatenate([section.le.xyz[:-1],section.ps.xyz[:-1],section.te.xyz[:-1],section.ss.xyz[::-1][:-1]])
    le_index=min(len(section.le.r)//2,len(section.le.r)-2)
    te_index=len(section.le.r)-1+len(section.ps.r)-1+min(len(section.te.r)//2,len(section.te.r)-2)
    # Degenerate sharp-edge arcs collapse to one vertex rather than repeated nodes.
    keep=np.r_[True,np.linalg.norm(np.diff(xyz,axis=0),axis=1)>1e-12]
    indices=np.flatnonzero(keep)
    xyz=xyz[keep]
    if len(xyz)<3:raise ValueError("A blade profile requires at least three distinct vertices.")
    markers={max(0,int(np.searchsorted(indices,index,side='right')-1)):name
             for index,name in ((le_index,'le'),(te_index,'te'))}
    return np.vstack([xyz,xyz[0]]),markers


def _external_xyz(xyz,settings):
    # Cyclic permutations preserve handedness when rotating the internal Z axis.
    order={"Z":[0,1,2],"X":[2,0,1],"Y":[1,2,0]}
    scale={"MM":1.,"CM":.1,"M":.001}
    if settings.rotation_axis not in order or settings.geometry_unit not in scale:
        raise ValueError("TurboGrid requires axis X/Y/Z and units MM/CM/M.")
    return xyz[:,order[settings.rotation_axis]]*scale[settings.geometry_unit]


def _coordinates(xyz,digits,markers=None):
    if not np.isfinite(xyz).all():raise ValueError("Cannot export NaN/Infinity coordinates.")
    return "".join(" ".join(format_number(float(v),digits) for v in row)
                   +(" "+markers[i] if markers and i in markers else "")+"\n" for i,row in enumerate(xyz))


def _validate_profile_coordinates(coordinates):
    """Validate the actual rounded file, without changing its points or precision."""
    lines=[line.split() for line in coordinates.splitlines()]
    rounded=np.asarray([[float(value) for value in line[:3]] for line in lines])
    if (rounded.ndim!=2 or rounded.shape[1]!=3 or len(rounded)<4
            or not np.isfinite(rounded).all()
            or not np.array_equal(rounded[0],rounded[-1])
            or np.any(np.linalg.norm(np.diff(rounded,axis=0),axis=1)==0)):
        raise ValueError("Blade profile collapses or is not closed at the selected output precision.")
    markers=[(index,line[3]) for index,line in enumerate(lines) if len(line)==4]
    if (any(len(line) not in (3,4) for line in lines)
            or sorted(name for _,name in markers)!=['le','te']
            or any(index==len(lines)-1 for index,_ in markers)
            or np.array_equal(rounded[markers[0][0]],rounded[markers[1][0]])):
        raise ValueError("Blade profile requires distinct LE/TE markers at the selected output precision.")
    return len(rounded)


def prepare_turbogrid_export(params):
    """Return validated filenames/bytes without creating or updating any files."""
    from ..models.blade_rows import validate_rows, row_parameters
    validate_rows(params)
    project=params
    row=(next(row for row in params.blade_rows if row.identifier == params.active_blade_row)
         if params.blade_rows is not None else None)
    if row is not None and row.kind=='meridional':
        raise ValueError('TurboGrid blade export requires a bladed element; meridional-only elements have no profiles.')
    stator=row is not None and row.kind == "diffuser"
    if stator:params=row_parameters(project,row)
    elif row is not None:
        from ..geometry.tip_clearance import has_tip_clearance
        row_clearance=row.parameters.tip_clearance
        if (has_tip_clearance(row.parameters) or row_clearance is not None and row_clearance.analysis_le_mm is not None) and params.tip_clearance!=row_clearance:
            raise ValueError('Active Impeller Tip clearance disagrees with its row snapshot. Reselect the row before export.')
        if params.splitter!=row.parameters.splitter:
            raise ValueError('Active Impeller Splitter disagrees with its row snapshot. Reselect the row before export.')
        if row.independent_meridional:params=row_parameters(project,row)
    if not stator:
        from ..fileio.trim_export_guard import guard_trim_export
        guard_trim_export(params)
        if row is not None:guard_trim_export(row.parameters)
    geometry=generate_diffuser_3d(params) if stator else generate_impeller(params)
    splitter=not stator and params.splitter is not None
    edges=params.diffuser_edges if stator else params.impeller_edges
    analysis=geometry.analysis_shroud
    analysis_intervals=None
    if analysis is not None:
        analysis_intervals=export_wall_intervals(project,geometry,edges)
        if splitter:export_wall_intervals(project,replace(geometry,sections=geometry.splitter_sections),edges)
        from ..geometry.analysis_shroud import analysis_export_geometry
        geometry=analysis_export_geometry(geometry)
    if splitter and (not geometry.splitter_sections or [s.span for s in geometry.splitter_sections]!=[s.span for s in geometry.sections]):
        raise ValueError('Splitter export requires matching Main and Splitter span sections.')
    clearance=not stator and geometry.tip is not None
    if clearance:
        from ..geometry.span_extension import extend_tip_to_shroud
        split_sections=geometry.splitter_sections
        if splitter:
            split_sections=[*split_sections,extend_tip_to_shroud(replace(geometry,sections=split_sections))]
        geometry=replace(geometry,sections=[*geometry.sections,extend_tip_to_shroud(geometry)],splitter_sections=split_sections)
    edges=params.diffuser_edges if stator else params.impeller_edges
    settings=params.turbogrid;digits=params.export.significant_digits
    filenames=[settings.hub_curve_filename,settings.shroud_curve_filename,settings.profile_curve_filename,"BladeGen.inf"]
    if len(set(name.lower() for name in filenames))!=4 or any(not name or Path(name).name!=name or any(c in name for c in '\\/:\r\n') for name in filenames):
        raise ValueError("TurboGrid filenames must be distinct simple filenames.")
    contents={}
    intervals = export_wall_intervals(project, geometry, edges) if analysis_intervals is None else [
        analysis_intervals[0],tuple(np.interp(analysis_intervals[1],analysis.drawing_m,analysis.wall.m))]
    if analysis is not None and clearance:
        for sections in (geometry.sections,geometry.splitter_sections or []):
            if not sections:continue
            distances=np.concatenate([getattr(sections[-1],'master_'+role).meridional_distance for role in ('le','ps','te','ss')])
            start,end=intervals[1];tolerance=geometry.shroud.length*1e-6
            if distances.min()<start-tolerance or distances.max()>end+tolerance:
                raise ValueError('Analysis Shroud extension exceeds the assigned wall interval.')
    if splitter and analysis_intervals is None:
        export_wall_intervals(project,replace(geometry,sections=geometry.splitter_sections),edges)
    for (wall,p,name),(start,end) in zip(((geometry.hub,params.hub,filenames[0]),(geometry.shroud,params.shroud,filenames[1])), intervals):
        distances=np.linspace(start,end,p.export_points)
        corners=corner_distances(p,wall)
        if len(corners):distances=np.unique(np.r_[distances,corners[(corners>start)&(corners<end)]])
        zr=sample_meridional(wall,distances)
        xyz=np.column_stack((zr[:,1],np.zeros(len(zr)),zr[:,0]))
        contents[name]=_coordinates(_external_xyz(xyz,settings),digits)
    profiles=[]
    groups=[('Main',geometry.sections)]+([('Splitter',geometry.splitter_sections)] if splitter else [])
    for name,sections in groups:
        if splitter:profiles.append(f'## {name}\n')
        profile_counts=[]
        for index,section in enumerate(sections):
            label="Hub" if section.span==0 else "Tip" if section.span==1 else f"Span_{section.span:.15g}"
            if clearance and index==len(sections)-2:label="Tip_clearance"
            if clearance and index==len(sections)-1:label="Shroud_extension"
            xyz,markers=closed_profile(section)
            coordinates=_coordinates(_external_xyz(xyz,settings),digits,markers)
            profile_counts.append(_validate_profile_coordinates(coordinates))
            profiles.append(f"# {label}\n"+coordinates)
        if len(set(profile_counts))!=1:
            raise ValueError(f"{name} blade profiles must have matching contour point counts.")
    contents[filenames[2]]="".join(profiles)
    def end_type(choice,side):
        if choice not in ('auto','EllipseEnd','CutOffEnd','SquareEnd'):
            raise ValueError("Unknown TurboGrid edge end type.")
        if choice!='auto':return choice
        sections=[params.diffuser_profile] if stator else params.sections
        kinds=[getattr(s.edge_parameters,side+'_type') for s in sections]
        if all(k==EdgeType.CUTOFF for k in kinds):return 'CutOffEnd'
        if all(k!=EdgeType.CUTOFF for k in kinds):return 'EllipseEnd'
        return None  # Mixed span shapes use curve markers and TurboGrid detection.
    edge_lines=''
    for blade in range(len(groups)):
        for side,choice in (('le',settings.leading_edge_type),('te',settings.trailing_edge_type)):
            kind=end_type(choice,side)
            if kind:edge_lines+=f"Blade {blade} {side.upper()}: {kind}\n"
    contents["BladeGen.inf"]=("!======  CFX-BladeGen Export  ========\n"
        f"Axis of Rotation: {settings.rotation_axis}\nNumber of Blade Sets: {params.geometry.vane_count}\n"
        f"Number of Blades Per Set: {len(groups)}\nGeometry Units: {settings.geometry_unit}\n"
        +edge_lines+f"Hub Data File: {filenames[0]}\n"
        f"Shroud Data File: {filenames[1]}\nProfile Data File: {filenames[2]}\n")
    if splitter:
        direction='Right Handed' if params.rotation_direction.sign==1 else 'Left Handed'
        contents["BladeGen.inf"]+=f'! Main is Blade 0; Splitter is Blade 1. Set Machine Data Theta Direction to {direction}.\n'
    if clearance:
        contents["BladeGen.inf"]+=(
            f"! Physical Tip: Profile Number {len(geometry.sections)-1} (1-based, Tip_clearance).\n"
            "! Set Shroud Tip / Tip Option = Profile Number in TurboGrid to restore the physical gap.\n"
            "! The final Shroud_extension profile is for spanwise surface continuation only.\n")
        if splitter:contents['BladeGen.inf']+='! Apply the physical Tip profile number to both Main and Splitter.\n'
    if analysis is not None:
        contents['BladeGen.inf']+='! Analysis Shroud selected; physical blade Tip and drawing casing are unchanged.\n'
    # Preserve the platform text-file newlines used by the original writer.
    return filenames,{name:content.replace('\n',os.linesep).encode('ascii') for name,content in contents.items()}


def export_turbogrid(case_directory,params):
    from .case_publish import publish_case_files
    filenames,contents=prepare_turbogrid_export(params)
    publish_case_files(case_directory,contents)
    target=Path(case_directory)
    return [target/name for name in filenames]
