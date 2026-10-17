from copy import deepcopy
import json
import numpy as np
import pytest
from blade_designer.geometry.provisional_disk import make_provisional_disk
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.models.parameters import BladeParameters
from blade_designer.models.cad import validate_cad_parameters
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.cad.client import prepare_job
from blade_designer.models.blade_rows import initial_rows


def test_provisional_dimensions_are_explicit_and_do_not_change_design():
    p=BladeParameters();before=deepcopy(p);g=generate_impeller(p)
    disk=make_provisional_disk(p)
    assert p==before and disk.provisional
    assert disk.bore_radius_mm==10
    assert disk.backside.start_z==pytest.approx(75)
    root_radius=max(float(getattr(g.sections[0],'master_'+role).r.max()) for role in ('le','ps','te','ss'))
    assert disk.backside.start_r==pytest.approx(root_radius+10)
    assert disk.front_end_m_mm<=g.hub.length
    assert disk.backside.segments[0].length==pytest.approx(disk.backside.start_r-10)


def test_provisional_json_roundtrip_and_legacy_optional_fields(tmp_path):
    p=BladeParameters();p.cad_export.disk=make_provisional_disk(p);p.cad_export.fillet.hub_radius_mm=2.5
    path=tmp_path/'provisional.json';save_project(path,p)
    assert load_project(path)==p
    assert json.loads(path.read_text(encoding='utf-8'))['cad_export']['disk']['provisional'] is True
    p.cad_export.disk.provisional=False;p.cad_export.disk.front_end_m_mm=None
    save_project(path,p);disk=json.loads(path.read_text(encoding='utf-8'))['cad_export']['disk']
    assert 'provisional' not in disk and 'front_end_m_mm' not in disk


def test_provisional_mechanical_front_does_not_reassign_turbogrid_walls(tmp_path):
    p=BladeParameters();p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
    for curve in (p.hub,p.shroud):
        for segment in curve.segments:segment.blade_row='row-2'
    before=deepcopy(p);disk=make_provisional_disk(p)
    assert p==before
    p.blade_rows[0].parameters.cad_export.disk=disk
    job=prepare_job(p,'mechanical',tmp_path/'job');r=json.loads((job/'request.json').read_text(encoding='utf-8'))
    assert r['domain_error'] and r['mechanical_hub_segments']
    assert r['settings']['disk']['provisional']
    assert all(segment.blade_row=='row-2' for segment in p.hub.segments)


@pytest.mark.parametrize('end',[None,-1,float('nan'),True])
def test_incomplete_provisional_parameters_rejected(end):
    p=BladeParameters();p.cad_export.disk=make_provisional_disk(p);p.cad_export.disk.front_end_m_mm=end
    with pytest.raises(ValueError):validate_cad_parameters(p.cad_export)


def test_stale_provisional_front_rejected(tmp_path):
    p=BladeParameters();p.cad_export.disk=make_provisional_disk(p)
    p.cad_export.disk.front_end_m_mm=1
    with pytest.raises(ValueError,match='仮ディスク'):prepare_job(p,'mechanical',tmp_path/'stale')


def test_blade_blend_instructions_follow_radius_and_disabled_state():
    from blade_designer.fileio.turbogrid_cad_export import blade_blend_instructions
    text=blade_blend_instructions(3.25,False)
    assert '3.25 mm' in text and 'Hub Blend: disabled' in text
