"""Non-writing export input diagnostics. No Qt/OCP imports."""
from copy import deepcopy
from dataclasses import asdict,dataclass
import hashlib
from blade_designer.models.blade_rows import validate_rows,row_parameters
from blade_designer.models.cad import validate_cad_parameters,MechanicalExportScope
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.geometry.row_domain import export_wall_intervals
from blade_designer.geometry.tip_clearance import has_tip_clearance
from blade_designer.fileio.trim_export_guard import guard_trim_export
from blade_designer.cad.client import backend_python,json_text
from blade_designer.cad.errors import BackendUnavailableError


@dataclass(frozen=True)
class Check:
    code:str
    state:str
    message:str


@dataclass(frozen=True)
class Route:
    name:str
    checks:tuple[Check,...]

    @property
    def status(self):
        return 'BLOCKED' if any(c.state=='BLOCKED' for c in self.checks) else 'INPUTS_READY'


@dataclass(frozen=True)
class Readiness:
    row_name:str
    kind:str
    snapshot_hash:str
    routes:tuple[Route,...]
    note:str='Input diagnostics only. CAD generation, full 3D collision checks and ANSYS Import/Mesh were not run.'


def assess_exports(project,prepare_profiles=None):
    """prepare_profiles must validate/format data without creating any files."""
    if prepare_profiles is None:
        from blade_designer.fileio.turbogrid_export import prepare_turbogrid_export
        prepare_profiles=prepare_turbogrid_export
    original=deepcopy(project)
    digest=hashlib.sha256(json_text({'schema_version':'0.4',**asdict(original)}).encode('utf-8')).hexdigest()
    try:
        validate_rows(original)
        selected=next(r for r in original.blade_rows if r.identifier==original.active_blade_row) if original.blade_rows is not None else None
        params=row_parameters(original,selected) if selected is not None else original
    except (ValueError,StopIteration) as exc:
        check=Check('selection','BLOCKED',str(exc))
        return Readiness('Unavailable','unknown',digest,tuple(Route(name,(check,)) for name in ('Profile Points','Mechanical STEP','TurboGrid CAD')))
    kind=selected.kind if selected is not None else 'impeller'
    name=selected.name if selected is not None else 'Impeller'
    checks={route:[] for route in ('Profile Points','Mechanical STEP','TurboGrid CAD')}
    def check(routes,code,operation,success):
        try:operation();item=Check(code,'PASS',success)
        except (ValueError,ArithmeticError) as exc:item=Check(code,'BLOCKED',str(exc))
        for route in routes:checks[route].append(item)
    all_routes=tuple(checks)
    def require(condition,message):
        if not condition:raise ValueError(message)
    stator=kind=='diffuser'
    check(('Mechanical STEP','TurboGrid CAD'),'kind',lambda:require(not stator,'CAD currently supports Impeller rows only.'),'Impeller CAD supported.')
    if not stator:
        check(all_routes,'trim',lambda:guard_trim_export(params),'No unsupported trim export.')
        check(('Profile Points',),'splitter',lambda:require(params.splitter is None,'Splitter Profile Points export is not supported.'),'No unsupported splitter Profile Points.')
    geometry=None
    if any(c.code=='trim' and c.state=='BLOCKED' for c in checks['Profile Points']):
        for route in all_routes:checks[route].append(Check('geometry','NOT_TESTED','Unsupported derivative export: no derived geometry was generated.'))
    else:
        try:
            geometry=generate_diffuser_3d(params) if stator else generate_impeller(params)
            for route in all_routes:checks[route].append(Check('geometry','PASS','Numeric sections generated. This does not prove full 3D collision freedom.'))
        except (ValueError,ArithmeticError) as exc:
            for route in all_routes:checks[route].append(Check('geometry','BLOCKED',str(exc)))
    if geometry is not None:
        edges=params.diffuser_edges if stator else params.impeller_edges
        check(('Profile Points','TurboGrid CAD'),'domain',lambda:export_wall_intervals(original,geometry,edges),'Owned walls contain LE/TE and the complete profile.')
        if not params.cad_export.disk.provisional and params.cad_export.mechanical_scope!=MechanicalExportScope.BLADE_ONLY:
            check(('Mechanical STEP',),'domain',lambda:export_wall_intervals(original,geometry,edges),'Mechanical assigned domain valid.')
    if not any(c.state=='BLOCKED' for c in checks['Profile Points']):
        check(('Profile Points',),'serialized',lambda:prepare_profiles(original),'Formatting, units, axis, closure, LE/TE and span counts validated.')
    if not stator:
        check(('Mechanical STEP',),'enabled',lambda:require(params.cad_export.mechanical_enabled and params.cad_export.step_enabled,'Mechanical STEP output is disabled in CAD settings.'),'Mechanical STEP enabled.')
        check(('TurboGrid CAD',),'enabled',lambda:require(params.cad_export.turbogrid_enabled and params.cad_export.step_enabled,'TurboGrid CAD/STEP output is disabled in CAD settings.'),'TurboGrid CAD enabled.')
        check(('Mechanical STEP','TurboGrid CAD'),'cad_settings',lambda:validate_cad_parameters(params.cad_export),'CAD settings valid.')
        if geometry is not None and params.cad_export.disk.provisional and not any(c.code=='cad_settings' and c.state=='BLOCKED' for c in checks['Mechanical STEP']):
            from blade_designer.geometry.provisional_disk import hub_blade_extent
            end=params.cad_export.disk.front_end_m_mm
            check(('Mechanical STEP','TurboGrid CAD'),'disk_extent',
                  lambda:require(end<=geometry.hub.length+1e-9 and end>=hub_blade_extent(geometry)-geometry.hub.length*1e-6,
                                 'Provisional disk front extent no longer contains the Hub blade; explicitly recreate disk dimensions.'),
                  'Provisional disk front extent contains the Hub blade.')
        try:path=backend_python();available=path.is_file()
        except (BackendUnavailableError,OSError):available=False
        check(('Mechanical STEP','TurboGrid CAD'),'backend',lambda:require(available,'Optional .venv-cad backend is not available.'),'Backend executable exists; kernel execution not performed.')
        for route in ('Mechanical STEP','TurboGrid CAD'):
            need_disk=route=='TurboGrid CAD' or params.cad_export.mechanical_scope!=MechanicalExportScope.BLADE_ONLY
            if need_disk:
                check((route,),'disk',lambda:require(params.cad_export.disk.backside is not None and params.cad_export.disk.bore_radius_mm is not None,'Set disk dimensions or explicitly create a provisional disk; diagnostics do not create one.'),'Disk dimensions provided.')
            note='Blade Only contains no disk union or root fillet.' if route=='Mechanical STEP' and not need_disk else f"Boolean, root R{params.cad_export.fillet.hub_radius_mm:g} and assembly interference require an actual CAD run."
            checks[route].append(Check('kernel','NOT_TESTED','BREP and STEP roundtrip have not been run by this diagnostic. '+note))
        check(('TurboGrid CAD',),'clearance',lambda:require(not has_tip_clearance(params),'Positive Tip clearance TurboGrid CAD is not supported.'),'No unsupported positive clearance CAD.')
        checks['TurboGrid CAD'].append(Check('conversion','NOT_TESTED','Supported-format conversion and ANSYS Import/Mesh are not tested.'))
    return Readiness(name,kind,digest,tuple(Route(route,tuple(items)) for route,items in checks.items()))
