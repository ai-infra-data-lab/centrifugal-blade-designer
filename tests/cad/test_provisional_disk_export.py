import numpy as np
import pytest
import json
from blade_designer.geometry.provisional_disk import make_provisional_disk
from blade_designer.models.blade_rows import initial_rows
from blade_designer.cad.client import publish_job
from .conftest import sample_parameters,run_job


def test_provisional_disk_and_arbitrary_root_radius_are_actual_cad(tmp_path):
    p=sample_parameters();p.cad_export.disk=make_provisional_disk(p)
    p.cad_export.fillet.hub_radius_mm=2.5
    result=run_job(p,tmp_path/'provisional','mechanical');r=result['report']
    assert r['overall']=='WARNING',r.get('error')
    assert r['disk_geometry_status']=='PROVISIONAL'
    assert r['fillet_status']=='PASS' and r['checks']['fillet']['main']['fillet_radius_mm']==2.5
    assert r['artifacts']['mechanical']['status']=='PASS'
    assert all('R2.5.step' in name for name in r['artifacts']['mechanical']['files'])
    step=r['artifacts']['mechanical']['roundtrip']
    assert all(face['status']=='PASS' for face in step['fillet_after_step']['faces'])
    disk=p.cad_export.disk
    expected=np.pi*(disk.backside.start_r**2-disk.bore_radius_mm**2)*20
    assert r['checks']['hub_solid']['volume_mm3']==pytest.approx(expected,rel=1e-9)
    target=tmp_path/'case';publish_job(result['job'],target,p)
    instructions=(target/'turbogrid/blade_blend_settings.md').read_text(encoding='utf-8')
    assert '2.5 mm' in instructions and 'Radius: 8 mm' not in instructions


def test_provisional_disk_never_bypasses_turbogrid_ownership(tmp_path):
    p=sample_parameters();p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
    for wall in (p.hub,p.shroud):
        for segment in wall.segments:segment.blade_row='row-2'
    row=p.blade_rows[0];row.parameters.cad_export.disk=make_provisional_disk(p)
    row.parameters.cad_export.fillet.hub_radius_mm=2.5
    result=run_job(p,tmp_path/'ownership','both');r=result['report']
    assert r['overall']=='FAIL' and 'TurboGrid' in r['error']['message']
    assert r['artifacts']['mechanical']['status']=='PASS'
    assert 'turbogrid_cad' not in r['artifacts']


def test_disk_only_has_valid_step_and_no_fillet_claim(tmp_path):
    p=sample_parameters();p.cad_export.disk=make_provisional_disk(p)
    result=run_job(p,tmp_path/'disk-only','disk');r=result['report']
    assert r['disk_geometry_status']=='PROVISIONAL' and r['solid_validity']=='PASS'
    assert r['fillet_status'].startswith('NOT_APPLICABLE')
    assert r['artifacts']['disk_only']['roundtrip']['status']=='PASS'
    preview=json.loads((result['job']/'preview.json').read_text(encoding='utf-8'))
    assert preview['scope']=='disk_only' and set(preview['triangles'])=={'HUB_DISK'}
