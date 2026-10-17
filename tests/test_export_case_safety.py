"""Publication safety. Synthetic bytes test I/O, not CAD geometry validity."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib,json
import pytest
from blade_designer.cad.client import publish_job,json_text
from blade_designer.models.parameters import BladeParameters
from blade_designer.fileio.turbogrid_export import export_turbogrid,prepare_turbogrid_export
from blade_designer.fileio.mechanical_step_export import publish_verified_artifact
from blade_designer.fileio import case_publish as cp,cad_validation_report


def contents(directory):
    return {p.relative_to(directory).as_posix():p.read_bytes() for p in directory.rglob('*') if p.is_file()}


def synthetic_job(tmp_path):
    p=BladeParameters();p.cad_export.turbogrid_enabled=False
    job=tmp_path/'job';job.mkdir()
    text=json_text({'schema_version':'0.4',**asdict(p)})
    digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
    (job/'geometry_snapshot.json').write_text(text,encoding='utf-8')
    names=['mechanical/main.step','mechanical/splitter.step']
    hashes={}
    for index,name in enumerate(names):
        path=job/'outputs'/name;path.parent.mkdir(parents=True,exist_ok=True)
        data=f'SYNTHETIC PUBLICATION SENTINEL {index}; NOT A CAD VALIDATION'.encode()
        path.write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    request={'parameter_snapshot_hash':digest,'action':'mechanical','settings':asdict(p.cad_export)}
    report={'overall':'PASS','parameter_snapshot_hash':digest,'artifacts':{'mechanical':{'status':'PASS','files':names,'sha256':hashes}}}
    (job/'request.json').write_text(json_text(request),encoding='utf-8')
    (job/'result.json').write_text(json_text(report),encoding='utf-8')
    return p,job,report


def existing_case(tmp_path):
    target=tmp_path/'case';(target/'mechanical').mkdir(parents=True)
    (target/'mechanical'/'main.step').write_bytes(b'old main')
    (target/'mechanical'/'splitter.step').write_bytes(b'old splitter')
    (target/'user.txt').write_bytes(b'keep user file')
    (target/'validation').mkdir();(target/'validation'/'cad_validation.json').write_bytes(b'old successful report')
    return target


def test_prepare_profile_bytes_is_non_writing_and_exact(tmp_path,monkeypatch):
    p=BladeParameters();before=deepcopy(p)
    files=export_turbogrid(tmp_path/'case',p)
    actual={f.name:f.read_bytes() for f in files}
    def forbidden(*args,**kwargs):raise AssertionError('prepare must not create or write files')
    for method in ('mkdir','write_bytes','write_text'):monkeypatch.setattr(Path,method,forbidden)
    names,prepared=prepare_turbogrid_export(p)
    assert prepared==actual and names==[f.name for f in files] and p==before


def test_turbogrid_installation_failure_never_mixes_generations(tmp_path,monkeypatch):
    p=BladeParameters();target=tmp_path/'case';files=export_turbogrid(target,p)
    before=contents(target);p.geometry.theta_le_deg=20
    original=cp.os.replace;failed=False
    def fail(source,destination):
        nonlocal failed
        if Path(destination)==target and not failed:failed=True;raise PermissionError('injected locked case')
        return original(source,destination)
    monkeypatch.setattr(cp.os,'replace',fail)
    with pytest.raises(PermissionError):export_turbogrid(target,p)
    assert failed and contents(target)==before
    assert [f.name for f in files]==['hub.curve','shroud.curve','profile.curve','BladeGen.inf']


def test_mechanical_payload_hashes_all_checked_before_publication(tmp_path):
    p,job,source=synthetic_job(tmp_path);target=existing_case(tmp_path);before=contents(target)
    (job/'outputs'/'mechanical'/'splitter.step').write_bytes(b'tampered second file')
    result=publish_job(job,target,p)
    assert result['overall']=='FAIL' and result['error']['stage']=='CASE PUBLICATION'
    assert result['artifacts']['mechanical']['publication']=='NOT_PUBLISHED'
    assert contents(target)==before
    assert (job/'publication_failure.json').is_file()


def test_metadata_failure_rolls_back_all_cad_files(tmp_path,monkeypatch):
    p,job,source=synthetic_job(tmp_path);target=existing_case(tmp_path);before=contents(target)
    def fail(*args,**kwargs):raise OSError('injected report disk failure')
    monkeypatch.setattr(cad_validation_report,'write_report',fail)
    result=publish_job(job,target,p)
    assert result['overall']=='FAIL' and contents(target)==before


def test_complete_cad_case_preserves_other_files_and_relative_paths(tmp_path):
    p,job,source=synthetic_job(tmp_path);target=existing_case(tmp_path)
    result=publish_job(job,target,p)
    assert result['overall']=='PASS'  # publication fixture; no geometry was executed
    for name in source['artifacts']['mechanical']['files']:
        assert (target/name).read_bytes()==(job/'outputs'/name).read_bytes()
    assert (target/'user.txt').read_bytes()==b'keep user file'
    assert (target/'validation'/'cad_validation.json').is_file()
    assert (target/'parameters'/'geometry_snapshot.json').read_text(encoding='utf-8')==(job/'geometry_snapshot.json').read_text(encoding='utf-8')
    assert '.stage' not in json.dumps(result)


def test_standalone_artifact_publication_rejects_tamper_and_aliases(tmp_path):
    p,job,source=synthetic_job(tmp_path);target=existing_case(tmp_path);before=contents(target)
    artifact=deepcopy(source['artifacts']['mechanical'])
    artifact['files'].append('MECHANICAL/main.step')
    from blade_designer.cad.errors import CadExportError
    with pytest.raises(CadExportError):publish_verified_artifact(job,target,artifact)
    assert contents(target)==before


def test_snapshot_mismatch_preserves_existing_case_without_entering_transaction(tmp_path):
    p,job,source=synthetic_job(tmp_path);target=existing_case(tmp_path);before=contents(target)
    p.geometry.vane_count+=1
    with pytest.raises(ValueError,match='snapshot hash'):publish_job(job,target,p)
    assert contents(target)==before and not (tmp_path/'.case.publish.lock').exists()
