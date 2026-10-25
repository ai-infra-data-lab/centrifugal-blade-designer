"""CAD settings contain no kernel or Qt objects. Missing disk data stays missing."""
from dataclasses import dataclass,field
from enum import Enum
import math
from numbers import Real
from .meridional import MeridionalCurveParameters

class FilletMode(str,Enum):
    TRUE_CAD="true_cad"
    NONE="none"

class MechanicalExportScope(str,Enum):
    BLADE_ONLY="blade_only"
    BLADE_HUB="blade_hub"
    PERIODIC_SECTOR="periodic_sector"
    FULL_IMPELLER="full_impeller"

class SectorBoundaryMode(str,Enum):
    FIXED="fixed"
    BLADE_FOLLOWING="blade_following"

@dataclass
class FilletParameters:
    hub_enabled:bool=True
    shroud_enabled:bool=False
    hub_radius_mm:float=8.0
    mode:FilletMode=FilletMode.TRUE_CAD

@dataclass
class DiskGeometryParameters:
    backside:MeridionalCurveParameters|None=None
    bore_radius_mm:float|None=None
    provisional:bool=False
    front_end_m_mm:float|None=None

@dataclass
class CadExportParameters:
    mechanical_enabled:bool=True
    turbogrid_enabled:bool=True
    step_enabled:bool=True
    length_unit:str="mm"
    rotation_axis:str="Z"
    fillet:FilletParameters=field(default_factory=FilletParameters)
    disk:DiskGeometryParameters=field(default_factory=DiskGeometryParameters)
    mechanical_scope:MechanicalExportScope=MechanicalExportScope.BLADE_HUB
    surface_tolerance_mm:float=0.01
    sector_boundary:SectorBoundaryMode=SectorBoundaryMode.FIXED


def validate_cad_parameters(settings):
    if not isinstance(settings,CadExportParameters) or not isinstance(settings.fillet,FilletParameters) or not isinstance(settings.disk,DiskGeometryParameters):
        raise ValueError("Invalid CAD parameter objects.")
    for value in (settings.mechanical_enabled,settings.turbogrid_enabled,settings.step_enabled,settings.fillet.hub_enabled,settings.fillet.shroud_enabled):
        if type(value) is not bool:raise ValueError("CAD enable flags must be boolean.")
    if settings.length_unit!="mm" or settings.rotation_axis!="Z":raise ValueError("CAD currently requires mm and rotation axis Z.")
    if not isinstance(settings.mechanical_scope,MechanicalExportScope) or not isinstance(settings.fillet.mode,FilletMode):raise ValueError("Unknown CAD scope or fillet mode.")
    if not isinstance(settings.sector_boundary,SectorBoundaryMode):raise ValueError("Unknown sector boundary mode.")
    if settings.fillet.shroud_enabled:raise ValueError("Shroud CAD fillet is not supported for the open impeller.")
    for value in (settings.surface_tolerance_mm,settings.fillet.hub_radius_mm):
        if not isinstance(value,Real) or isinstance(value,bool) or not math.isfinite(value) or value<=0:raise ValueError("CAD tolerance and fillet radius must be finite and positive.")
    bore=settings.disk.bore_radius_mm
    if bore is not None and (not isinstance(bore,Real) or isinstance(bore,bool) or not math.isfinite(bore) or bore<0):raise ValueError("Disk bore radius must be finite and nonnegative, or unset.")
    if settings.disk.backside is not None and not isinstance(settings.disk.backside,MeridionalCurveParameters):raise ValueError("Invalid disk backside curve.")
    if type(settings.disk.provisional) is not bool:raise ValueError("Disk provisional flag must be boolean.")
    end=settings.disk.front_end_m_mm
    if settings.disk.provisional:
        if settings.disk.backside is None or bore is None or not isinstance(end,Real) or isinstance(end,bool) or not math.isfinite(end) or end<=0:
            raise ValueError("A provisional disk requires explicit backside, bore and positive front extent.")
    elif end is not None:raise ValueError("A custom mechanical front extent requires the provisional disk flag.")
