"""Analytic notification intervals and real read-only CLI failure boundaries."""
import json
import hashlib
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
import pytest
from tools.analyze_cad_timing import analyze_events, read_trace

ROOT = Path(__file__).resolve().parents[1]


def trace():
    return [{'time': 10, 'kind': 'worker', 'type': 'CadExportWorker', 'job': 'wheel'},
        {'time': 11, 'kind': 'stage', 'stage': 'PREPARATION'},
        {'time': 12, 'kind': 'stage', 'stage': 'FULL IMPELLER'},
        {'time': 20, 'kind': 'completed', 'overall': 'WARNING', 'cancelled': None},
        {'time': 21, 'kind': 'fresh_gui_export_verified', 'job': 'wheel', 'seconds': 10.5}]


def test_analytic_accounting_and_independent_gui_clock_without_mutating_events():
    events = trace(); original = deepcopy(events)
    result = analyze_events(events); job = result['cad_jobs'][0]
    assert events == original
    assert job['observed_job_seconds'] == job['accounted_seconds'] == 10
    assert [(row['stage'], row['seconds']) for row in job['intervals']] == [
        ('BEFORE FIRST STAGE', 1), ('PREPARATION', 1), ('FULL IMPELLER', 8)]
    assert job['stage_totals'][0]['percent_of_observed_job'] == 80
    assert job['gui_reported_seconds'] == 10.5
    assert result['geometry_validation'] == 'NOT_ASSESSED'
    assert result['analysis_status'] == 'PARSED' and job['recorded_overall'] == 'WARNING'


def test_warning_without_gui_verification_is_not_promoted_to_gui_success():
    job = analyze_events(trace()[:-1])['cad_jobs'][0]
    assert job['complete'] and not job['gui_verification_event_seen']
    assert job['gui_reported_seconds'] is None


def test_cancelled_and_provisional_work_are_not_combined_with_generation():
    events = [dict(time=0, kind='worker', type='ProvisionalDiskWorker', job='disk'),
        dict(time=1, kind='stage', stage='PROVISIONAL DISK'),
        dict(time=2, kind='completed', overall='PASS'),
        dict(time=2, kind='worker', type='CadExportWorker', job='cancel'),
        dict(time=3, kind='completed', overall='FAIL', cancelled=True),
        dict(time=3, kind='cancellation_verified', previous_case_unchanged=True), *trace()]
    jobs = analyze_events(events)['cad_jobs']
    assert [row['job'] for row in jobs] == ['cancel', 'wheel']
    assert jobs[0]['cancelled'] and jobs[0]['observed_job_seconds'] == 1
    assert not jobs[0]['gui_verification_event_seen']
    assert jobs[1]['observed_job_seconds'] == 10


def test_incomplete_and_zero_duration_jobs_do_not_get_invented_totals_or_percentages():
    job = analyze_events(trace()[:3])['cad_jobs'][0]
    assert not job['complete'] and job['observed_job_seconds'] is None
    assert job['cancelled'] is None
    assert job['accounted_seconds'] == 2 and job['open_stage'] == 'FULL IMPELLER'
    assert all(row['percent_of_observed_job'] is None for row in job['stage_totals'])
    zero = analyze_events([trace()[0], dict(time=10, kind='completed', overall='FAIL')])['cad_jobs'][0]
    assert zero['observed_job_seconds'] == 0
    assert all(row['percent_of_observed_job'] is None for row in zero['stage_totals'])


def test_step_counters_are_grouped_but_not_labeled_as_pure_cpu_time():
    result = analyze_events([trace()[0], dict(time=11, kind='stage', stage='STEP BOUNDARY A: 2/4'),
        dict(time=12, kind='stage', stage='STEP BOUNDARY A: 4/4'),
        dict(time=15, kind='completed', overall='PASS')])
    assert result['cad_jobs'][0]['stage_totals'][0]['stage'] == 'STEP BOUNDARY PROGRESS / FINALIZATION'
    assert result['cad_jobs'][0]['stage_totals'][0]['seconds'] == 4
    assert any('finalization' in text for text in result['limitations'])


@pytest.mark.parametrize('bad', [None, True, -1, float('nan'), float('inf'), '10'])
def test_invalid_timestamps_are_rejected(bad):
    events = trace(); events[0]['time'] = bad
    with pytest.raises(ValueError, match='Event 1: time'): analyze_events(events)


@pytest.mark.parametrize('events', [
    [None], [], [dict(time=1, kind='stage', stage='orphan')],
    [dict(time=1, kind='completed', overall='PASS')],
    [trace()[0], {**trace()[1], 'time': 9}],
    [trace()[0], {**trace()[0], 'time': 11}],
    [trace()[0], dict(time=11, kind='stage', stage='')],
    [trace()[0], dict(time=11, kind='completed', overall='UNKNOWN')],
    [trace()[0], dict(time=11, kind='completed', overall='PASS', cancelled=True)],
    [trace()[0], dict(time=11, kind='completed', overall='FAIL', cancelled='yes')],
    [trace()[0], dict(time=11, kind='future_schema')],
    [{**trace()[0], 'type': 'UnknownWorker'}],
    trace()[:2] + [dict(time=12, kind='fresh_gui_export_verified', job='wheel', seconds=2)],
    trace() + [{**trace()[-1], 'time': 22}],
    trace()[:4] + [{**trace()[-1], 'seconds': float('nan')}],
    trace()[:4] + [{**trace()[-1], 'job': 'unrelated'}],
    trace()[:4] + [{**trace()[0], 'time': 21}],
])
def test_invalid_or_ambiguous_event_sequences_fail_closed(events):
    with pytest.raises(ValueError): analyze_events(events)


def cli(*args):
    return subprocess.run([sys.executable, '-X', 'utf8', 'tools/analyze_cad_timing.py', *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=20)


def test_real_cli_multiple_traces_and_new_output_preserve_source_bytes(tmp_path):
    first = tmp_path/'first.jsonl'; second = tmp_path/'second.jsonl'
    first.write_text('\n'.join(json.dumps(row) for row in trace()), encoding='utf-8-sig')
    other = trace()
    for row in other:
        if row.get('job') == 'wheel': row['job'] = 'other'
    second.write_text('\n'.join(json.dumps(row) for row in other), encoding='utf-8')
    before = first.read_bytes(), second.read_bytes()
    output = tmp_path/'timing.json'
    result = cli(first, second, '--json-output', output)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding='utf-8'))
    assert len(report['profiles']) == 2
    assert report['profiles'][0]['source_sha256'] == hashlib.sha256(before[0]).hexdigest()
    assert 'NOT assessed' in result.stdout
    assert (first.read_bytes(), second.read_bytes()) == before
    saved = output.read_bytes()
    assert cli(first, '--json-output', output).returncode == 2
    assert output.read_bytes() == saved
    assert cli(first, '--json-output', first).returncode == 2
    assert first.read_bytes() == before[0]


def test_cli_malformed_duplicate_and_untimestamped_inputs_do_not_write_outputs(tmp_path):
    source = tmp_path/'trace.jsonl'; output = tmp_path/'must-not-exist.json'
    for content in ('not JSON\n', 'BLADE_CAD:{"stage":"FULL IMPELLER"}\n', '\n'):
        source.write_text(content, encoding='utf-8')
        result = cli(source, '--json-output', output)
        assert result.returncode == 2 and 'invalid JSON event' in result.stderr
        assert not output.exists()
    source.write_text('\n'.join(json.dumps(row) for row in trace()), encoding='utf-8')
    result = cli(source, source, '--json-output', output)
    assert result.returncode == 2 and 'double counting' in result.stderr
    assert not output.exists()
    broken = tmp_path/'broken.jsonl'; broken.write_text('{}\n[]\n', encoding='utf-8')
    with pytest.raises(ValueError): read_trace(broken)
