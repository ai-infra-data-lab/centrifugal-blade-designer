from copy import deepcopy
import json
import subprocess
import sys
import numpy as np
import pytest

from blade_designer.fileio.preview_job import queue_preview,calculate_preview,read_preview
from blade_designer.fileio.project_io import load_project
from blade_designer.geometry.preview_computation import prepare_preview,prepare_row_previews
from blade_designer.models.blade_rows import row_parameters
from blade_designer.models.parameters import BladeParameters
from test_preview_computation import ROOT,assert_exact


@pytest.mark.parametrize('identifier',['row-1','row-2','row-3'])
def test_worker_results_match_selected_default_engines_and_all_rows(tmp_path,identifier):
    project=load_project(ROOT/'blade_designer/defaults/default_project.json')
    row=next(r for r in project.blade_rows if r.identifier==identifier)
    params=row_parameters(project,row);before=deepcopy(params)
    # Include a full project in another test; this one exercises active snapshots.
    job=queue_preview(params,row.kind,True,tmp_path/'job')
    result=calculate_preview(job);assert result['phase']=='PREVIEW_READY'
    actual=read_preview(job,params,row.kind,True)
    expected=(prepare_preview(params,row.kind,include_legacy=True),prepare_row_previews(params))
    assert_exact(actual,expected);assert params==before
    assert not list(job.glob('*.part.*'))


def test_full_project_row_identity_and_independent_counts_survive_child(tmp_path):
    project=load_project(ROOT/'blade_designer/defaults/default_project.json')
    job=queue_preview(project,'diffuser',True,tmp_path/'job')
    code="""
import sys
from blade_designer.fileio.preview_job import calculate_preview
calculate_preview(sys.argv[1])
assert not any(k.startswith(('PySide6','pyqtgraph','OCP')) for k in sys.modules)
"""
    completed=subprocess.run([sys.executable,'-c',code,str(job)],capture_output=True,text=True,timeout=30)
    assert completed.returncode==0,completed.stderr
    selected,rows=read_preview(job,project,'diffuser',True)
    assert selected.selected_error is None
    assert [r[:2] for r in rows.entries]==[(r.identifier,r.name) for r in project.blade_rows]
    assert [r[3] for r in rows.entries]==[r.parameters.geometry.vane_count for r in project.blade_rows]


@pytest.mark.parametrize('damage',['snapshot','kind','rows','payload','result','cancel','missing'])
def test_stale_incomplete_or_modified_results_are_not_adopted(tmp_path,damage):
    params=BladeParameters();job=queue_preview(params,'impeller',False,tmp_path/'job');calculate_preview(job)
    if damage=='snapshot':params.geometry.vane_count+=1
    if damage=='kind':
        with pytest.raises(ValueError):read_preview(job,params,'diffuser',False)
        return
    if damage=='rows':
        with pytest.raises(ValueError):read_preview(job,params,'impeller',True)
        return
    if damage=='payload':(job/'payload.json').write_text('{}')
    if damage in ('result','cancel'):
        report=json.loads((job/'result.json').read_text())
        report.update({'phase':'pending'} if damage=='result' else {'cancelled':True})
        (job/'result.json').write_text(json.dumps(report))
    if damage=='missing':(job/'result.json').unlink()
    with pytest.raises((ValueError,OSError)):read_preview(job,params,'impeller',False)


def test_numerical_failure_is_a_completed_diagnostic_not_a_valid_geometry(tmp_path):
    params=BladeParameters();params.impeller_edges.trailing_edge.hub_m_flow_norm=.01
    job=queue_preview(params,'impeller',True,tmp_path/'job');calculate_preview(job)
    selected,rows=read_preview(job,params,'impeller',True)
    assert selected.selected_error is not None and rows is None
    assert selected.legacy is not None


def test_valid_digest_does_not_make_an_incomplete_selected_result_valid(tmp_path):
    import hashlib
    from blade_designer.fileio import preview_payload
    params=BladeParameters();job=queue_preview(params,'impeller',False,tmp_path/'job');calculate_preview(job)
    selected,_=read_preview(job,params,'impeller',False);selected.area=None
    payload=preview_payload.dumps((selected,None));(job/'payload.json').write_bytes(payload)
    report=json.loads((job/'result.json').read_text());report['payload_hash']=hashlib.sha256(payload).hexdigest()
    (job/'result.json').write_text(json.dumps(report))
    with pytest.raises(ValueError,match='Incomplete selected'):read_preview(job,params,'impeller',False)
