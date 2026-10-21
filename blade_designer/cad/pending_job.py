"""Deferred numeric CAD snapshots; independent of Qt and the CAD kernel."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib,json,os,sys,traceback,uuid
from .client import ROOT,json_text,prepare_job,segment_points
from ..models.blade_rows import validate_rows,row_parameters
from ..models.cad import validate_cad_parameters
from ..geometry.meridional_segments import generate_meridional


def queue_job(project,action="generate",job_directory=None):
    """Freeze cheap input only. Geometry generation belongs to the worker."""
    if action not in ('generate','disk','mechanical','turbogrid','both'):
        raise ValueError('Unknown CAD action.')
    project=deepcopy(project);validate_rows(project);params=project
    if project.blade_rows is not None:
        row=next(row for row in project.blade_rows if row.identifier==project.active_blade_row)
        if row.kind!='impeller':raise ValueError('CAD export currently requires an Impeller blade row.')
        params=row_parameters(project,row)
    from ..fileio.trim_export_guard import guard_trim_export
    guard_trim_export(params);validate_cad_parameters(params.cad_export)
    text=json_text({'schema_version':'0.4',**asdict(project)})
    disk=params.cad_export.disk
    mechanical=None
    if disk.provisional:
        hub=generate_meridional(params.hub)
        if disk.front_end_m_mm>hub.length+1e-9:
            raise ValueError('Provisional disk front exceeds the Hub wall.')
        mechanical=segment_points(hub,0.,min(disk.front_end_m_mm,hub.length))
    request={'action':action,'parameter_snapshot_hash':hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'settings':asdict(params.cad_export),'mechanical_hub_segments':mechanical,
        'preparation_pending':True}
    job=Path(job_directory) if job_directory is not None else ROOT/'artifacts'/'cad-runs'/uuid.uuid4().hex
    job.mkdir(parents=True,exist_ok=False)
    (job/'geometry_snapshot.json').write_text(text,encoding='utf-8')
    (job/'request.json').write_text(json_text(request),encoding='utf-8')
    return job


def finish_preparation(job):
    """Build in a private child directory; promote the complete request last."""
    from ..fileio.project_io import _decode_v03
    job=Path(job);source=(job/'geometry_snapshot.json').read_bytes()
    pending=(job/'request.json').read_bytes();request=json.loads(pending)
    if request.get('preparation_pending') is not True:
        raise ValueError('CAD snapshot is not awaiting preparation.')
    # Match prepare_job's canonical LF text digest on Windows as well.
    expected=hashlib.sha256(json_text(json.loads(source)).encode('utf-8')).hexdigest()
    if expected!=request['parameter_snapshot_hash']:
        raise ValueError('Pending CAD snapshot hash mismatch.')
    if (job/'geometry.npz').exists():
        raise ValueError('Pending job already contains numeric geometry; create a new job.')
    project=_decode_v03(json.loads(source),row_snapshot=True)
    prepared=prepare_job(project,request['action'],job/'prepared_numeric')
    ready=json.loads((prepared/'request.json').read_text(encoding='utf-8'))
    if (ready['parameter_snapshot_hash']!=expected or
            (prepared/'geometry_snapshot.json').read_bytes()!=source or
            (job/'geometry_snapshot.json').read_bytes()!=source or
            (job/'request.json').read_bytes()!=pending):
        raise ValueError('CAD input changed during numeric preparation.')
    ready['preparation_pending']=False
    (prepared/'request.json').write_text(json_text(ready),encoding='utf-8')
    os.replace(prepared/'geometry.npz',job/'geometry.npz')
    os.replace(prepared/'request.json',job/'request.json')
    return job


def main():
    job=Path(sys.argv[1]).resolve()
    try:
        print('BLADE_CAD:'+json.dumps({'stage':'NUMERIC SNAPSHOT PREPARATION','pid':os.getpid()}),flush=True)
        finish_preparation(job)
        print('BLADE_CAD:'+json.dumps({'stage':'NUMERIC SNAPSHOT READY'}),flush=True)
        return 0
    except Exception as exc:
        result={'overall':'FAIL','error':{'type':type(exc).__name__,'stage':'NUMERIC PREPARATION',
            'message':str(exc)},'artifacts':{}}
        (job/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
        (job/'result.json').write_text(json_text(result),encoding='utf-8')
        return 1


if __name__=='__main__':sys.exit(main())
