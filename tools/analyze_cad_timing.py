"""Read-only analysis of timestamped native GUI acceptance JSONL traces.

Intervals are between observed notifications, not CPU/function timings or CAD
validation. Untimestamped process.log files cannot establish elapsed time.
"""
import argparse
import hashlib
import io
import json
import math
from numbers import Real
from pathlib import Path
import sys


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be a finite nonnegative number.')
    return float(value)


def text_field(record, name):
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Nonempty {name} is required.')
    return value


def stage_group(name):
    if name.startswith('STEP BOUNDARY '):
        return 'STEP BOUNDARY PROGRESS / FINALIZATION'
    return name


def analyze_events(records):
    jobs = []
    identifiers = set()
    active = None
    previous = None

    def interval(end):
        seconds = number(end - active['cursor'], 'interval')
        active['intervals'].append({'stage': active['stage'], 'seconds': seconds})

    def finish(end=None, overall=None, cancelled=None):
        if end is not None:
            interval(end)
        grouped = {}
        for row in active['intervals']:
            label = stage_group(row['stage'])
            grouped.setdefault(label, []).append(row['seconds'])
        durations = {label: math.fsum(values) for label, values in grouped.items()}
        total = end - active['start'] if end is not None else None
        accounted = math.fsum(durations.values())
        if total is not None and not math.isclose(total, accounted, rel_tol=1e-12, abs_tol=1e-6):
            raise ValueError('Timing intervals do not account for the observed job duration.')
        jobs.append({'job': active['job'], 'complete': end is not None,
            'recorded_overall': overall, 'cancelled': cancelled,
            'gui_verification_event_seen': False, 'gui_reported_seconds': None,
            'observed_job_seconds': total, 'accounted_seconds': accounted,
            'open_stage': active['stage'] if end is None else None,
            'intervals': active['intervals'],
            'stage_totals': [{'stage': label, 'seconds': seconds,
                'percent_of_observed_job': seconds / total * 100 if total else None}
                for label, seconds in sorted(durations.items(), key=lambda row: (-row[1], row[0]))]})

    for line, record in enumerate(records, 1):
        try:
            if not isinstance(record, dict):
                raise ValueError('Each event must be an object.')
            stamp = number(record.get('time'), 'time')
            if previous is not None and stamp < previous:
                raise ValueError('Timestamps moved backwards; wall-clock durations are unreliable.')
            previous = stamp
            kind = text_field(record, 'kind')
            if kind == 'worker':
                if active is not None:
                    raise ValueError('Overlapping workers or a missing completion event.')
                worker = text_field(record, 'type')
                if worker not in ('CadExportWorker', 'ProvisionalDiskWorker'):
                    raise ValueError('Unsupported worker type; refusing silent omission.')
                job = text_field(record, 'job')
                if job in identifiers:
                    raise ValueError('Duplicate worker job identifier.')
                identifiers.add(job)
                active = {'cad': worker == 'CadExportWorker', 'job': job, 'start': stamp,
                    'cursor': stamp, 'stage': 'BEFORE FIRST STAGE', 'intervals': []}
            elif kind == 'stage':
                if active is None:
                    raise ValueError('Stage event has no active worker.')
                stage = text_field(record, 'stage')
                if active['cad']:
                    interval(stamp)
                active.update(cursor=stamp, stage=stage)
            elif kind == 'completed':
                if active is None:
                    raise ValueError('Completion event has no active worker.')
                overall = record.get('overall')
                cancelled = record.get('cancelled')
                if overall not in ('PASS', 'WARNING', 'FAIL') or (cancelled is not None and type(cancelled) is not bool):
                    raise ValueError('Invalid recorded completion outcome.')
                if cancelled and overall != 'FAIL':
                    raise ValueError('Cancelled completion must record FAIL.')
                if active['cad']:
                    finish(stamp, overall, cancelled is True)
                active = None
            elif kind == 'fresh_gui_export_verified':
                job = text_field(record, 'job')
                matches = [row for row in jobs if row['job'] == job]
                if len(matches) != 1 or matches[0]['cancelled'] or matches[0]['recorded_overall'] not in ('PASS', 'WARNING'):
                    raise ValueError('GUI verification has no eligible completed CAD job.')
                row = matches[0]
                if row['gui_verification_event_seen']:
                    raise ValueError('Duplicate GUI verification event.')
                row.update(gui_verification_event_seen=True,
                    gui_reported_seconds=number(record.get('seconds'), 'GUI reported duration'))
            elif kind != 'cancellation_verified':
                raise ValueError(f'Unsupported event kind: {kind}')
        except (ValueError, OverflowError) as exc:
            raise ValueError(f'Event {line}: {exc}') from exc
    if active is not None and active['cad']:
        finish()
    if not jobs:
        raise ValueError('No CadExportWorker observations found.')
    return {'analysis_status': 'PARSED', 'clock': 'recorded wall-clock notifications',
        'geometry_validation': 'NOT_ASSESSED', 'cad_jobs': jobs,
        'limitations': ['Stage intervals can include several operations, process startup and GUI completion handling.',
            'STEP progress intervals include subsequent finalization; these are not isolated STEP CPU timings.',
            'Forward wall-clock adjustments cannot be detected from these events alone.',
            'Recorded PASS/WARNING and GUI verification events are observations, not independent geometry certification.',
            'Incomplete and cancelled jobs must not be used as completed-generation speed measurements.']}


def read_trace(path):
    records = []
    raw = Path(path).read_bytes()
    with io.StringIO(raw.decode('utf-8-sig'), newline=None) as stream:
        for line, value in enumerate(stream, 1):
            try:
                records.append(json.loads(value))
            except (ValueError, TypeError) as exc:
                raise ValueError(f'{path}, line {line}: invalid JSON event.') from exc
    result = analyze_events(records)
    return {'source': str(Path(path).resolve()), 'source_sha256': hashlib.sha256(raw).hexdigest(), **result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('events', nargs='+', type=Path)
    parser.add_argument('--json-output', type=Path, help='Create a new report; an existing file is never overwritten.')
    args = parser.parse_args(argv)
    try:
        profiles = [read_trace(path) for path in args.events]
        jobs = [row['job'] for profile in profiles for row in profile['cad_jobs']]
        if len(set(jobs)) != len(jobs):
            raise ValueError('Duplicate CAD jobs across input traces; refusing double counting.')
        result = {'schema_version': 1, 'profiles': profiles}
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
        if args.json_output:
            with args.json_output.open('x', encoding='utf-8') as stream:
                stream.write(payload)
    except (OSError, ValueError, OverflowError) as exc:
        print(f'CAD timing analysis failed: {exc}', file=sys.stderr)
        return 2
    for profile in profiles:
        print(profile['source'])
        for row in profile['cad_jobs']:
            print(f"  {row['job']}: recorded={row['recorded_overall']}, cancelled={row['cancelled']}, "
                  f"complete={row['complete']}, GUI verification event={row['gui_verification_event_seen']}")
            if row['observed_job_seconds'] is None:
                print(f"    INCOMPLETE: open stage={row['open_stage']}; total duration is unknown.")
            for stage in row['stage_totals'][:6]:
                percent = stage['percent_of_observed_job']
                share = f'{percent:.1f}%' if percent is not None else 'share unknown'
                print(f"    {stage['seconds']:.3f} s ({share}): {stage['stage']}")
    print('Notification intervals only; CAD validity, CPU timings and speedup are NOT assessed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
