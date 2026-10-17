from pathlib import Path
import os,tempfile
from ..cad.client import json_text


def write_report(directory,report,failed_suffix=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    stem="cad_validation" if failed_suffix is None else "cad_validation_failed_"+failed_suffix
    payloads={stem+".json":json_text(report),stem+".txt":f"Overall: {report['overall']}\n"+"\n".join(f"{name}: {value.get('status','NOT_TESTED')}" for name,value in report.get('artifacts',{}).items())+"\n"+str(report.get("error",""))+"\n"}
    for name,text in payloads.items():
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=directory,delete=False) as stream:stream.write(text);temporary=Path(stream.name)
        try:os.replace(temporary,directory/name)
        finally:temporary.unlink(missing_ok=True)
