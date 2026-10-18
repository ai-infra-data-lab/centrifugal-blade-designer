"""Run existing tests without touching old caches or the system temp directory."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import uuid
import argparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
QUICK_TESTS = [
    'tests/test_camber.py', 'tests/test_distributions.py',
    'tests/test_meridional_line.py', 'tests/test_meridional_arc.py',
    'tests/test_surface_evaluation.py', 'tests/test_surface_diagnostics.py',
]


def summarize_report(path):
    """Count actual JUnit cases; collection errors remain errors, not passes."""
    counts = dict(passed=0, failed=0, errors=0, skipped=0)
    problems = []
    try:
        root = ET.parse(path).getroot()
        for case in root.iter('testcase'):
            outcome = ('errors' if case.find('error') is not None else
                       'failed' if case.find('failure') is not None else
                       'skipped' if case.find('skipped') is not None else 'passed')
            counts[outcome] += 1
            if outcome in ('errors', 'failed'):
                problems.append(case.get('classname', '')+'::'+case.get('name', ''))
        return dict(counts, report_status='read', problems=problems)
    except (OSError, ET.ParseError) as exc:
        return dict(counts, report_status='unavailable', report_error=str(exc), problems=[])


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--brief', action='store_true')
    parser.add_argument('--suite', choices=('quick', 'full'))
    options, pytest_args = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    if options.suite and pytest_args:
        parser.error('--suite selects a fixed suite; use explicit pytest arguments without --suite.')
    selected = QUICK_TESTS if options.suite == 'quick' else pytest_args or ['tests']
    run = ROOT / "artifacts" / "test-runs" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    temporary = run / "tmp"
    temporary.mkdir()
    environment = os.environ.copy()
    environment["PYTEST_DEBUG_TEMPROOT"] = str(temporary)
    environment["PYTHONUTF8"] = "1"
    command = [sys.executable, "-m", "pytest", "-q", "-W", "error",
               "-p", "no:cacheprovider", "--junitxml=" + str(run / "pytest.xml")]
    command.extend(selected)
    log = run / 'pytest.log'
    if options.brief:
        with log.open('wb') as stream:
            result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT)
    else:
        result = subprocess.run(command, cwd=ROOT, env=environment)
    summary = summarize_report(run / 'pytest.xml')
    collecting = '--collect-only' in selected or '--co' in selected
    exit_code = result.returncode
    # A normal test run without a usable report is not verified, even if the
    # child unexpectedly exits zero. Preserve pytest's nonzero error codes.
    informational = any(arg in selected for arg in ('--help', '-h', '--version', '-V'))
    if not informational and not exit_code and summary['report_status'] != 'read':
        exit_code = 2
    (run / "result.json").write_text(json.dumps({
        "command": command, "python": sys.version, "returncode": result.returncode,
        "test_temp": str(temporary), 'runner_returncode': exit_code,
        'suite': options.suite or ('explicit' if pytest_args else 'full'),
        'collection_only': collecting, 'summary': summary,
        'log': str(log) if options.brief else None,
    }, indent=2) + "\n", encoding="utf-8")
    label = 'COLLECTION ONLY' if collecting else 'Tests'
    print(f"{label}: passed={summary['passed']} failed={summary['failed']} "
          f"errors={summary['errors']} skipped={summary['skipped']} exit={exit_code}")
    if summary['report_status'] != 'read':
        print('JUnit report unavailable; see raw output. '+summary.get('report_error', ''))
    for problem in summary['problems'][:10]:
        print('Problem:', problem)
    if len(summary['problems']) > 10:
        print(f"{len(summary['problems'])-10} additional problems in JUnit/raw output.")
    if options.brief:
        print('Raw log:', log)
    print("Test report:", run)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
