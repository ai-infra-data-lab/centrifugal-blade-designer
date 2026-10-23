"""Private provisional-disk calculation; no Qt, CAD kernel or public output."""
from dataclasses import asdict,fields
from pathlib import Path
import hashlib,json,os,sys,traceback,uuid
from .client import ROOT,json_text,verified_snapshot_text
from ..geometry.provisional_disk import make_provisional_disk
from ..models.cad import CadExportParameters,DiskGeometryParameters,validate_cad_parameters


def snapshot_hash(project):
    return hashlib.sha256(json_text({'schema_version':'0.4',**asdict(project)}).encode('utf-8')).hexdigest()


def queue_disk_job(project,job_directory=None):
    text=json_text({'schema_version':'0.4',**asdict(project)})
    job=Path(job_directory) if job_directory is not None else ROOT/'artifacts'/'cad-runs'/('disk-'+uuid.uuid4().hex)
    job.mkdir(parents=True,exist_ok=False)
    (job/'geometry_snapshot.json').write_text(text,encoding='utf-8')
    (job/'request.json').write_text(json_text({'disk_preparation_pending':True,
        'parameter_snapshot_hash':hashlib.sha256(text.encode('utf-8')).hexdigest()}),encoding='utf-8')
    return job


def calculate_disk(job):
    from ..fileio.project_io import _decode_v03
    job=Path(job);request_bytes=(job/'request.json').read_bytes();request=json.loads(request_bytes)
    if request.get('disk_preparation_pending') is not True:raise ValueError('Not a provisional disk job.')
    source=verified_snapshot_text(job,request['parameter_snapshot_hash'])
    project=_decode_v03(json.loads(source),row_snapshot=True)
    disk=make_provisional_disk(project)
    if (job/'request.json').read_bytes()!=request_bytes or verified_snapshot_text(job,request['parameter_snapshot_hash'])!=source:
        raise ValueError('Provisional disk input changed during calculation.')
    data=asdict(disk)
    result={'overall':'PASS','artifacts':{},'phase':'PROVISIONAL_DISK_READY',
        'parameter_snapshot_hash':request['parameter_snapshot_hash'],'disk':data,
        'disk_sha256':hashlib.sha256(json_text(data).encode('utf-8')).hexdigest()}
    temporary=job/'disk_result.part.json';temporary.write_text(json_text(result),encoding='utf-8')
    os.replace(temporary,job/'result.json')
    return result


def read_disk_result(job,project):
    from ..fileio.project_io import _curve
    job=Path(job);expected=snapshot_hash(project)
    request=json.loads((job/'request.json').read_text(encoding='utf-8'))
    if request.get('disk_preparation_pending') is not True or request.get('parameter_snapshot_hash')!=expected:
        raise ValueError('Provisional disk request snapshot mismatch.')
    verified_snapshot_text(job,expected)
    result=json.loads((job/'result.json').read_text(encoding='utf-8'))
    if (result.get('overall')!='PASS' or result.get('cancelled') or
            result.get('phase')!='PROVISIONAL_DISK_READY' or result.get('parameter_snapshot_hash')!=expected):
        raise ValueError('Provisional disk calculation is incomplete or stale.')
    data=result.get('disk')
    if not isinstance(data,dict) or set(data)!={f.name for f in fields(DiskGeometryParameters)}:
        raise ValueError('Invalid provisional disk fields.')
    if hashlib.sha256(json_text(data).encode('utf-8')).hexdigest()!=result.get('disk_sha256'):
        raise ValueError('Provisional disk result digest mismatch.')
    data=dict(data);data['backside']=_curve(data['backside']);disk=DiskGeometryParameters(**data)
    # Dimension generation does not validate unrelated CAD/fillet choices.
    # The subsequent CAD queue retains its own complete validation.
    validate_cad_parameters(CadExportParameters(disk=disk))
    if not disk.provisional:raise ValueError('Expected provisional disk dimensions.')
    return disk


def main():
    job=Path(sys.argv[1]).resolve()
    try:
        print('BLADE_CAD:'+json.dumps({'stage':'PROVISIONAL DISK CALCULATION','pid':os.getpid()}),flush=True)
        calculate_disk(job)
        return 0
    except Exception as exc:
        (job/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
        (job/'result.json').write_text(json_text({'overall':'FAIL','artifacts':{},
            'error':{'type':type(exc).__name__,'message':str(exc)}}),encoding='utf-8')
        return 1


if __name__=='__main__':sys.exit(main())
