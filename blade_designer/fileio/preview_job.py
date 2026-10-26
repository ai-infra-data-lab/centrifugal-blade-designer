"""Private numerical preview process. No Qt, CAD kernel, or public output."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
import uuid

from . import preview_payload
from .snapshot_compat import canonical_sector_defaults
from ..geometry.preview_computation import prepare_preview, prepare_row_previews, PreviewComputation, RowPreviews
from ..models.geometry import BladeGeometry
from ..models.geometry_3d import ImpellerGeometry
from ..models.flow_area import FlowAreaResult

ROOT=Path(__file__).resolve().parents[2]


def snapshot_text(params):
    payload=canonical_sector_defaults({"schema_version":"0.4",**asdict(params)})
    return json.dumps(payload,allow_nan=False,sort_keys=True,
                      default=lambda v:v.value if hasattr(v,"value") else v.item())


def _digest(data):return hashlib.sha256(data).hexdigest()


def _bounded(path,limit):
    with Path(path).open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Preview file limit exceeded.')
    return data


def queue_preview(params,kind,include_rows=False,job_directory=None):
    if kind not in ("impeller","diffuser",'meridional') or type(include_rows) is not bool:
        raise ValueError("Invalid preview request.")
    data=snapshot_text(params).encode("utf-8")
    if len(data)>4*1024*1024:raise ValueError("Preview snapshot limit exceeded.")
    job=Path(job_directory) if job_directory is not None else ROOT/"artifacts"/"preview-runs"/uuid.uuid4().hex
    job.mkdir(parents=True,exist_ok=False)
    (job/"snapshot.json").write_bytes(data)
    (job/"request.json").write_text(json.dumps({"snapshot_hash":_digest(data),"kind":kind,
        "include_rows":include_rows}),encoding="utf-8")
    return job


def _input(job):
    job=Path(job)
    request_bytes=_bounded(job/"request.json",32768);request=json.loads(request_bytes)
    if (not isinstance(request,dict) or set(request)!={"snapshot_hash","kind","include_rows"}
            or request["kind"] not in ("impeller","diffuser",'meridional') or type(request["include_rows"]) is not bool):
        raise ValueError("Invalid preview request.")
    data=_bounded(job/"snapshot.json",4*1024*1024)
    if _digest(data)!=request["snapshot_hash"]:
        raise ValueError("Preview snapshot mismatch.")
    return request_bytes,request,data


def calculate_preview(job):
    from .project_io import _decode_v03
    job=Path(job);request_bytes,request,data=_input(job)
    params=_decode_v03(json.loads(data),row_snapshot=True)
    selected=prepare_preview(params,request["kind"],include_legacy=True)
    rows=prepare_row_previews(params) if request["include_rows"] and selected.selected_error is None else None
    payload=preview_payload.dumps((selected,rows))
    if _input(job)!=(request_bytes,request,data):raise ValueError("Preview input changed during computation.")
    part=job/"payload.part.json";part.write_bytes(payload);os.replace(part,job/"payload.json")
    result={"overall":"PASS","phase":"PREVIEW_READY","snapshot_hash":request["snapshot_hash"],
            "kind":request["kind"],"include_rows":request["include_rows"],"payload_hash":_digest(payload)}
    part=job/"result.part.json";part.write_text(json.dumps(result),encoding="utf-8");os.replace(part,job/"result.json")
    return result


def read_preview(job,params,kind,include_rows):
    job=Path(job);_,request,_=_input(job)
    if request!={"snapshot_hash":_digest(snapshot_text(params).encode("utf-8")),"kind":kind,"include_rows":include_rows}:
        raise ValueError("Stale preview request.")
    result=json.loads(_bounded(job/"result.json",32768))
    if (not isinstance(result,dict) or result.get("overall")!="PASS" or result.get("phase")!="PREVIEW_READY"
            or result.get("cancelled") or any(result.get(k)!=v for k,v in request.items())):
        raise ValueError("Incomplete or stale preview result.")
    with (job/"payload.json").open("rb") as stream:payload=stream.read(preview_payload.MAX_BYTES+1)
    if len(payload)>preview_payload.MAX_BYTES or _digest(payload)!=result.get("payload_hash"):
        raise ValueError("Invalid preview payload digest.")
    value=preview_payload.loads(payload)
    if (not isinstance(value,tuple) or len(value)!=2 or not isinstance(value[0],PreviewComputation)
            or (value[1] is not None and not isinstance(value[1],RowPreviews))
            or (include_rows and value[0].selected_error is None and value[1] is None)
            or (not include_rows and value[1] is not None)):
        raise ValueError("Invalid preview result type.")
    selected=value[0]
    if (any(v is not None and not isinstance(v,str) for v in
            (selected.selected_error,selected.legacy_error,selected.reference_error))
            or (selected.legacy is not None and not isinstance(selected.legacy,BladeGeometry))):
        raise ValueError("Invalid preview diagnostics.")
    if selected.selected_error is None:
        wall=selected.meridional if kind=='meridional' else selected.impeller if kind=='impeller' else selected.diffuser
        if not isinstance(wall,ImpellerGeometry) or not isinstance(selected.area,FlowAreaResult):
            raise ValueError("Incomplete selected preview geometry.")
    return value


def main():
    job=Path(sys.argv[1]).resolve()
    try:calculate_preview(job);return 0
    except Exception as exc:
        (job/"error.log").write_text(traceback.format_exc(),encoding="utf-8")
        (job/"result.json").write_text(json.dumps({"overall":"FAIL","error":{"message":str(exc)}}),encoding="utf-8")
        return 1


if __name__=="__main__":sys.exit(main())
