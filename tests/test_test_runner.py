"""Exercise the real CLI and pytest exit codes, including collection errors."""
import json
import subprocess
import sys
import os
from pathlib import Path
import pytest
from tools.run_tests import ROOT, QUICK_TESTS, summarize_report


@pytest.mark.parametrize('source,code,counts,detail', [
    ('def test_ok(): pass\n', 0, (1, 0, 0, 0), '1 passed'),
    ('def test_bad(): assert False, "KEEP_FAILURE_DETAIL"\n', 1, (0, 1, 0, 0), 'KEEP_FAILURE_DETAIL'),
    ('import pytest\n@pytest.mark.skip(reason="KEEP_SKIP")\ndef test_skip(): pass\n', 0, (0, 0, 0, 1), '1 skipped'),
    ('import module_that_does_not_exist_for_runner_probe\n', 2, (0, 0, 1, 0), 'ModuleNotFoundError'),
    ('def test_warning():\n import warnings\n warnings.warn("KEEP_WARNING")\n', 1, (0, 1, 0, 0), 'KEEP_WARNING'),
])
def test_brief_preserves_outcomes_raw_detail_and_environment(tmp_path, source, code, counts, detail):
    test = tmp_path/'test_runner_probe.py'
    test.write_text(source, encoding='utf-8')
    result = subprocess.run([sys.executable, 'tools/run_tests.py', '--brief', str(test)],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=45)
    assert result.returncode == code, result.stdout+result.stderr
    run = Path(result.stdout.split('Test report: ')[-1].strip())
    metadata = json.loads((run/'result.json').read_text(encoding='utf-8'))
    summary = metadata['summary']
    assert tuple(summary[k] for k in ('passed','failed','errors','skipped')) == counts
    assert metadata['returncode'] == metadata['runner_returncode'] == code
    assert metadata['test_temp'] == str(run/'tmp')
    assert metadata['command'][:3] == [sys.executable, '-m', 'pytest']
    assert '-W' in metadata['command'] and 'no:cacheprovider' in metadata['command']
    assert detail in (run/'pytest.log').read_text(encoding='utf-8')
    assert 'KEEP_FAILURE_DETAIL' not in result.stdout


@pytest.mark.parametrize('content', [None, '<broken'])
def test_missing_or_malformed_xml_is_not_reported_as_success(tmp_path, content):
    path = tmp_path/'pytest.xml'
    if content is not None: path.write_text(content, encoding='utf-8')
    result = summarize_report(path)
    assert result['report_status'] == 'unavailable'
    assert result['passed'] == 0
    assert result['report_error']


def test_quick_suite_is_explicit_non_gui_existing_files():
    assert len(QUICK_TESTS) == len(set(QUICK_TESTS))
    assert all((ROOT/p).is_file() and '/cad/' not in p and '_gui' not in p for p in QUICK_TESTS)


def test_collection_only_is_labelled_not_tested(tmp_path):
    test = tmp_path/'test_collect_probe.py'
    test.write_text('def test_must_not_run(): raise AssertionError("EXECUTED")\n', encoding='utf-8')
    result = subprocess.run([sys.executable,'tools/run_tests.py','--brief','--collect-only',str(test)],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'COLLECTION ONLY' in result.stdout
    run = Path(result.stdout.split('Test report: ')[-1].strip())
    assert json.loads((run/'result.json').read_text(encoding='utf-8'))['collection_only']


def test_existing_explicit_invocation_keeps_console_output(tmp_path):
    test = tmp_path/'test_console_probe.py'
    test.write_text('def test_ok(): pass\n', encoding='utf-8')
    result = subprocess.run([sys.executable,'tools/run_tests.py',str(test)],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert result.returncode == 0
    assert '1 passed' in result.stdout and 'Test report:' in result.stdout


def test_no_tests_selected_preserves_pytest_exit_five(tmp_path):
    test = tmp_path/'test_empty_probe.py'
    test.write_text('def test_ok(): pass\n', encoding='utf-8')
    result = subprocess.run([sys.executable,'tools/run_tests.py','--brief',str(test),'-k','does_not_match'],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert result.returncode == 5
    assert 'passed=0' in result.stdout and 'exit=5' in result.stdout


def test_fixed_suite_cannot_silently_accept_subset_arguments():
    result = subprocess.run([sys.executable,'tools/run_tests.py','--suite','quick','-k','missing'],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert result.returncode == 2
    assert 'fixed suite' in result.stderr


def test_cli_paths_remain_utf8_when_parent_python_utf8_mode_is_disabled(tmp_path):
    test = tmp_path/'test_encoding_probe.py'
    test.write_text('def test_ok(): pass\n',encoding='utf-8')
    env = os.environ.copy()
    env['PYTHONUTF8'] = '0'
    env['PYTHONIOENCODING'] = 'cp932'
    result = subprocess.run([sys.executable,'tools/run_tests.py','--brief',str(test)],
                            cwd=ROOT,env=env,capture_output=True,timeout=45)
    assert result.returncode == 0
    text = result.stdout.decode('utf-8')
    assert str(ROOT/'artifacts/test-runs') in text
