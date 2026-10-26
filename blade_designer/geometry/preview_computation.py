"""Numerical preview preparation, independent of Qt and file formats.

This service preserves the existing engines and sampling settings. Results are
owned by the caller; this is a synchronous boundary, not a background worker.
"""
from copy import deepcopy
from dataclasses import dataclass, field

from ..models.blade_rows import initial_rows, row_parameters
from ..models.flow_area import FlowAreaResult
from ..models.geometry import BladeGeometry
from ..models.geometry_3d import ImpellerGeometry
from ..models.meridional import MeridionalGeometry
from ..models.parameters import BladeParameters
from .designer import BladeDesigner
from .flow_area import calculate_flow_area
from .row_domain import preview_wall_chunks


@dataclass
class PreviewComputation:
    legacy: BladeGeometry | None = None
    legacy_error: str | None = None
    impeller: ImpellerGeometry | None = None
    diffuser: ImpellerGeometry | None = None
    reference_error: str | None = None
    area: FlowAreaResult | None = None
    selected_error: str | None = None
    meridional: ImpellerGeometry | None = None


@dataclass
class RowPreviews:
    entries: list[tuple[str, str, ImpellerGeometry, int]] = field(default_factory=list)
    analysis_chunks: list[MeridionalGeometry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    wall_chunks: dict | None = None


def prepare_preview(params: BladeParameters, kind: str, *,
                    include_legacy: bool = False, designer: BladeDesigner | None = None,
                    impeller: ImpellerGeometry | None = None) -> PreviewComputation:
    """Prepare selected geometry and gross area without changing input parameters.

    Legacy 2D and the reference Impeller may fail independently of a valid
    selected stator. A selected failure returns its diagnostic and any valid
    legacy result so the controller can retain its existing recovery policy.
    Programming errors deliberately propagate. Precomputed Impellers are reused.
    """
    if kind not in ("impeller", "diffuser",'meridional'):
        raise ValueError("Unknown preview row type.")
    params = deepcopy(params)
    designer = designer if designer is not None else BladeDesigner()
    result = PreviewComputation(impeller=impeller)
    active=next((row for row in params.blade_rows or [] if row.identifier==params.active_blade_row),None)
    if active is not None and active.independent_meridional:
        try:params=row_parameters(params,active)
        except (ValueError,ArithmeticError) as exc:
            result.selected_error=str(exc);return result
    if kind=='meridional':
        from .element_walls import generate_wall_element
        try:
            result.meridional=generate_wall_element(params)
            result.area=calculate_flow_area(result.meridional.hub,result.meridional.shroud,params.flow_path,
                points=params.resolution.area_points,strict=False,mean_points=params.resolution.mean_points)
        except (ValueError,ArithmeticError) as exc:result.selected_error=str(exc)
        return result
    if include_legacy:
        try:
            result.legacy = designer.generate_diffuser(params)
        except (ValueError, ArithmeticError) as exc:
            result.legacy_error = str(exc)
    try:
        if kind == "diffuser":
            result.diffuser = designer.generate_diffuser_3d(params)
        if result.impeller is None:
            try:
                result.impeller = designer.generate_3d(params)
            except (ValueError, ArithmeticError) as exc:
                if kind == "impeller":
                    raise
                result.reference_error = str(exc)
        wall = result.impeller if kind == "impeller" else result.diffuser
        result.area = calculate_flow_area(
            wall.hub, wall.shroud, params.flow_path,
            points=params.resolution.area_points, strict=False,
            mean_points=params.resolution.mean_points)
    except (ValueError, ArithmeticError) as exc:
        result.selected_error = str(exc)
    return result


def prepare_row_previews(params: BladeParameters, *,
                         designer: BladeDesigner | None = None) -> RowPreviews:
    """Prepare each row and its analysis walls as one indivisible display entry.

    A numerical failure omits only that row, including its wall chunks. Valid
    other rows remain available. No GUI state or persistent design is updated.
    """
    params = deepcopy(params)
    designer = designer if designer is not None else BladeDesigner()
    result = RowPreviews()
    independent=any(row.independent_meridional for row in params.blade_rows or [])
    if independent:result.wall_chunks={'hub':[],'shroud':[]}
    for row in params.blade_rows or initial_rows(params):
        try:
            p = row_parameters(params, row)
            if row.kind=='meridional':
                from .element_walls import generate_wall_element
                geometry=generate_wall_element(p)
            else:geometry = (designer.generate_3d(p) if row.kind == "impeller" else designer.generate_diffuser_3d(p))
            chunks = preview_wall_chunks(p, geometry, row.identifier).get("analysis_shroud", [])
            result.entries.append((row.identifier, row.name, geometry, 1 if row.kind=='meridional' else p.geometry.vane_count))
            if independent:
                walls=preview_wall_chunks(p,geometry,row.identifier)
                for key in ('hub','shroud'):result.wall_chunks[key].extend(walls[key])
            result.analysis_chunks.extend(chunks)
        except (ValueError, ArithmeticError) as exc:
            result.errors.append(f"ERROR — 3D {row.name}: {exc} (row omitted)")
    return result
