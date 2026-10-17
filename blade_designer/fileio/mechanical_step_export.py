"""Publish only staged, verified STEP bytes. Never construct geometry here."""
from pathlib import Path
import hashlib
from ..cad.errors import CadExportError
from .case_publish import publish_case_files,_write_case_files


def publish_verified_artifact(job,target,artifact):
    publish_case_files(target,_verified_artifact_contents(job,artifact))


def _write_verified_artifact(job,stage,artifact):
    """Called only inside the whole CAD case transaction."""
    _write_case_files(stage,_verified_artifact_contents(job,artifact))


def _verified_artifact_contents(job,artifact):
    job=Path(job).resolve();contents={};names=set()
    for name in artifact["files"]:
        if not isinstance(name,str):raise CadExportError("Invalid staged output path type.")
        relative=Path(name)
        key=relative.as_posix().casefold()
        if relative.anchor or ".." in relative.parts or not relative.parts or ':' in name or key in names:
            raise CadExportError("Invalid or duplicate staged output path.")
        names.add(key)
        source=(job/"outputs"/relative).resolve()
        if not source.is_relative_to(job/"outputs"):raise CadExportError("Staged output escapes the CAD job.")
        data=source.read_bytes()
        if not data or hashlib.sha256(data).hexdigest()!=artifact.get("sha256",{}).get(name):raise CadExportError("CAD output changed after validation: "+name)
        contents[name]=data
    if not contents:raise CadExportError("No verified CAD output files were provided.")
    return contents
