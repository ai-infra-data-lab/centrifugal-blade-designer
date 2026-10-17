"""Publish only staged, verified STEP bytes. Never construct geometry here."""
from pathlib import Path
import hashlib,os,tempfile
from ..cad.errors import CadExportError


def publish_verified_artifact(job,target,artifact):
    job=Path(job).resolve();target=Path(target).resolve();prepared=[]
    try:
        for name in artifact["files"]:
            relative=Path(name)
            if relative.is_absolute() or ".." in relative.parts:raise CadExportError("Invalid staged output path.")
            source=(job/"outputs"/relative).resolve()
            if not source.is_relative_to(job/"outputs"):raise CadExportError("Staged output escapes the CAD job.")
            data=source.read_bytes()
            if not data or hashlib.sha256(data).hexdigest()!=artifact.get("sha256",{}).get(name):raise CadExportError("CAD output changed after validation: "+name)
            destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile('wb',dir=destination.parent,delete=False) as stream:stream.write(data);temporary=Path(stream.name)
            prepared.append((temporary,destination))
        for temporary,destination in prepared:os.replace(temporary,destination)
    finally:
        for temporary,_ in prepared:temporary.unlink(missing_ok=True)
