"""TurboGrid ASCII XYZ curves and verified BladeGen initialization syntax.

Sources: Ansys 2026 R1 User Guide 2.1, 10.3.6 and official stator.zip.
LE/TE end keywords are from the 2.1 initialization example, not guessed.
"""
from pathlib import Path
import os
import tempfile
import numpy as np
from .csv_export import format_number
from ..geometry.meridional_segments import sample_meridional
from ..geometry.geometry_3d import generate_impeller
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


def export_turbogrid(case_directory,params):
    from ..models.blade_rows import validate_rows
    validate_rows(params)
    if params.blade_rows is not None and next(row for row in params.blade_rows if row.identifier == params.active_blade_row).kind != "impeller":
        raise ValueError("Select an Impeller blade row for TurboGrid export.")
    geometry=generate_impeller(params)
    settings=params.turbogrid;digits=params.export.significant_digits
    filenames=[settings.hub_curve_filename,settings.shroud_curve_filename,settings.profile_curve_filename,"BladeGen.inf"]
    if len(set(name.lower() for name in filenames))!=4 or any(not name or Path(name).name!=name or any(c in name for c in '\\/:\r\n') for name in filenames):
        raise ValueError("TurboGrid filenames must be distinct simple filenames.")
    contents={}
    intervals = export_wall_intervals(params, geometry)
    for (wall,p,name),(start,end) in zip(((geometry.hub,params.hub,filenames[0]),(geometry.shroud,params.shroud,filenames[1])), intervals):
        zr=sample_meridional(wall,np.linspace(start,end,p.export_points))
        xyz=np.column_stack((zr[:,1],np.zeros(len(zr)),zr[:,0]))
        contents[name]=_coordinates(_external_xyz(xyz,settings),digits)
    profiles=[]
    for section in geometry.sections:
        label="Hub" if section.span==0 else "Tip" if section.span==1 else f"Span_{section.span:.15g}"
        xyz,markers=closed_profile(section)
        profiles.append(f"# {label}\n"+_coordinates(_external_xyz(xyz,settings),digits,markers))
    contents[filenames[2]]="".join(profiles)
    def end_type(choice,side):
        if choice not in ('auto','EllipseEnd','CutOffEnd','SquareEnd'):
            raise ValueError("Unknown TurboGrid edge end type.")
        if choice!='auto':return choice
        kinds=[getattr(s.edge_parameters,side+'_type') for s in params.sections]
        if all(k==EdgeType.CUTOFF for k in kinds):return 'CutOffEnd'
        if all(k!=EdgeType.CUTOFF for k in kinds):return 'EllipseEnd'
        return None  # Mixed span shapes use curve markers and TurboGrid detection.
    edge_lines=''
    for side,choice in (('le',settings.leading_edge_type),('te',settings.trailing_edge_type)):
        kind=end_type(choice,side)
        if kind:edge_lines+=f"Blade 0 {side.upper()}: {kind}\n"
    contents["BladeGen.inf"]=("!======  CFX-BladeGen Export  ========\n"
        f"Axis of Rotation: {settings.rotation_axis}\nNumber of Blade Sets: {params.geometry.vane_count}\n"
        f"Number of Blades Per Set: 1\nGeometry Units: {settings.geometry_unit}\n"
        +edge_lines+f"Hub Data File: {filenames[0]}\n"
        f"Shroud Data File: {filenames[1]}\nProfile Data File: {filenames[2]}\n")
    # All geometry and formatting validated before creating any output.
    target=Path(case_directory);target.mkdir(parents=True,exist_ok=True)
    staged=[]
    try:
        for name,content in contents.items():
            with tempfile.NamedTemporaryFile('w',encoding='ascii',dir=target,delete=False) as stream:
                stream.write(content);staged.append((Path(stream.name),target/name))
        for source,destination in staged:os.replace(source,destination)
    finally:
        for source,destination in staged:
            if source.exists():source.unlink()
    return [target/name for name in filenames]
