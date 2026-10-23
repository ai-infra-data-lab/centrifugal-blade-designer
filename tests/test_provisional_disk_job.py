from copy import deepcopy
from dataclasses import asdict
import hashlib,json,subprocess,sys
import pytest
from blade_designer.cad.client import json_text
from blade_designer.cad.provisional_disk_job import queue_disk_job,calculate_disk,read_disk_result
from blade_designer.geometry.provisional_disk import make_provisional_disk
from blade_designer.models.parameters import BladeParameters


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    params=BladeParameters();before=deepcopy(params)
    job=queue_disk_job(params,tmp_path_factory.mktemp('disk')/'job')
    calculate_disk(job)
    assert params==before
    return params,{name:(job/name).read_bytes() for name in ('geometry_snapshot.json','request.json','result.json')}


@pytest.fixture
def job(tmp_path,prepared):
    for name,data in prepared[1].items():(tmp_path/name).write_bytes(data)
    return tmp_path


def test_same_dimensions_as_existing_calculation_and_no_input_mutation(job,prepared):
    params=deepcopy(prepared[0]);before=deepcopy(params)
    assert read_disk_result(job,params)==make_provisional_disk(params)
    assert params==before


def test_queue_never_computes_geometry(tmp_path,monkeypatch):
    import blade_designer.cad.provisional_disk_job as module
    monkeypatch.setattr(module,'make_provisional_disk',lambda p:pytest.fail('Geometry on queue caller'))
    job=queue_disk_job(BladeParameters(),tmp_path/'job')
    assert not (job/'result.json').exists() and not (job/'geometry.npz').exists()


@pytest.mark.parametrize('change',['source','request','result_hash','result_disk','missing','cancelled','phase'])
def test_modified_incomplete_or_cancelled_result_rejected(job,prepared,change):
    filename={'source':'geometry_snapshot.json','request':'request.json'}.get(change,'result.json')
    data=json.loads((job/filename).read_text(encoding='utf-8'))
    if change=='source':data['geometry']['vane_count']+=1
    elif change=='request':data['parameter_snapshot_hash']='wrong'
    elif change=='result_hash':data['parameter_snapshot_hash']='wrong'
    elif change=='result_disk':data['disk']['bore_radius_mm']+=1
    elif change=='missing':del data['disk']
    elif change=='cancelled':data['cancelled']=True
    else:data['phase']='NOT_READY'
    (job/filename).write_text(json_text(data),encoding='utf-8')
    with pytest.raises(ValueError):read_disk_result(job,prepared[0])


def test_invalid_but_rehashed_dimensions_rejected(job,prepared):
    data=json.loads((job/'result.json').read_text(encoding='utf-8'))
    data['disk']['front_end_m_mm']=-1
    data['disk_sha256']=hashlib.sha256(json_text(data['disk']).encode('utf-8')).hexdigest()
    (job/'result.json').write_text(json_text(data),encoding='utf-8')
    with pytest.raises(ValueError):read_disk_result(job,prepared[0])


def test_input_changed_during_calculation_cannot_complete(tmp_path,prepared,monkeypatch):
    import blade_designer.cad.provisional_disk_job as module
    job=queue_disk_job(prepared[0],tmp_path/'job');disk=read_disk_result_from_fixture(prepared)
    def changed(project):
        (job/'request.json').write_text('{}',encoding='utf-8');return disk
    monkeypatch.setattr(module,'make_provisional_disk',changed)
    with pytest.raises(ValueError,match='changed'):calculate_disk(job)
    assert not (job/'result.json').exists()


@pytest.mark.parametrize('setting',['shroud_enabled','hub_radius_mm'])
def test_disk_dimensions_do_not_validate_unrelated_cad_settings(tmp_path,prepared,monkeypatch,setting):
    import blade_designer.cad.provisional_disk_job as module
    params=deepcopy(prepared[0]);setattr(params.cad_export.fillet,setting,True if setting=='shroud_enabled' else -1)
    expected=read_disk_result_from_fixture(prepared)
    monkeypatch.setattr(module,'make_provisional_disk',lambda p:expected)
    job=queue_disk_job(params,tmp_path/'job');calculate_disk(job)
    assert read_disk_result(job,params)==expected


def test_actual_cli_reports_snapshot_failure_without_geometry_or_outputs(tmp_path):
    job=queue_disk_job(BladeParameters(),tmp_path/'job')
    (job/'geometry_snapshot.json').write_text('{}',encoding='utf-8')
    result=subprocess.run([sys.executable,'-X','utf8','-m','blade_designer.cad.provisional_disk_job',str(job)],
        capture_output=True,timeout=30)
    assert result.returncode==1
    report=json.loads((job/'result.json').read_text(encoding='utf-8'))
    assert report['overall']=='FAIL' and 'hash mismatch' in report['error']['message']
    assert not (job/'geometry.npz').exists() and not (job/'outputs').exists()


def read_disk_result_from_fixture(prepared):
    from blade_designer.fileio.project_io import _curve
    from blade_designer.models.cad import DiskGeometryParameters
    disk=json.loads(prepared[1]['result.json'])['disk'];disk['backside']=_curve(disk['backside'])
    return DiskGeometryParameters(**disk)


def test_actual_selected_python_child_needs_no_qt_or_cad(tmp_path):
    params=BladeParameters();job=queue_disk_job(params,tmp_path/'job')
    source=(job/'geometry_snapshot.json').read_bytes()
    code="from blade_designer.cad.provisional_disk_job import calculate_disk;import sys;calculate_disk(sys.argv[1]);assert not any(k.startswith(('PySide6','OCP')) for k in sys.modules)"
    result=subprocess.run([sys.executable,'-X','utf8','-c',code,str(job)],capture_output=True,timeout=60)
    assert result.returncode==0,result.stderr.decode('utf-8','replace')
    assert asdict(read_disk_result(job,params))==json.loads((job/'result.json').read_text())['disk']
    assert (job/'geometry_snapshot.json').read_bytes()==source
