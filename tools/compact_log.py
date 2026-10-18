"""Offline RTK filtering. pytest remains owned by run_tests.py, never RTK."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def filter_text(raw, filter_name):
    release = json.loads((ROOT/'tools/rtk-release.json').read_text(encoding='utf-8'))
    binary = ROOT/'artifacts/devtools/rtk/rtk.exe'
    if hashlib.sha256(binary.read_bytes()).hexdigest() != release['exe_sha256']:
        raise ValueError('RTK executable checksum mismatch.')
    env = os.environ.copy()
    env['RTK_DB_PATH'] = str(binary.parent/'tracking.db')
    env['RTK_TEE_DIR'] = str(binary.parent/'tee')
    env['RTK_RECALL'] = '0'
    env['RTK_TEE'] = '0'
    result = subprocess.run([str(binary),'pipe','--filter',filter_name],input=raw,
                            capture_output=True,text=True,encoding='utf-8',cwd=ROOT,env=env,timeout=30)
    if result.returncode:
        raise ValueError('RTK filter failed: '+result.stderr)
    if raw.strip() and not result.stdout.strip():
        raise ValueError('RTK returned empty output.')
    # Do not increase output size when compression is ineffective.
    return result.stdout if len(result.stdout.encode('utf-8')) < len(raw.encode('utf-8')) else raw


def render_output(raw, exit_code, summary, compress):
    """Never filter failed, errored, skipped, incomplete or zero-test results."""
    if (exit_code != 0 or summary.get('report_status') != 'read'
            or any(summary.get(k, 0) for k in ('failed','errors','skipped'))
            or summary.get('passed', 0) <= 0):
        return raw, False
    try:
        return compress(raw), True
    except (OSError, ValueError, subprocess.SubprocessError):
        return raw, False


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    sub.add_parser('pytest').add_argument('run_directory', type=Path)
    git_log = sub.add_parser('git-log')
    git_log.add_argument('--count', type=int, default=20)
    args = parser.parse_args(argv)
    if args.mode == 'pytest':
        run = args.run_directory.resolve()
        if not run.is_relative_to((ROOT/'artifacts/test-runs').resolve()):
            parser.error('Use a run_tests.py report inside this project artifacts/test-runs.')
        metadata = json.loads((run/'result.json').read_text(encoding='utf-8'))
        code = metadata.get('runner_returncode', metadata['returncode'])
        if type(code) is not int:
            parser.error('Invalid recorded pytest exit code.')
        raw = (run/'pytest.log').read_text(encoding='utf-8')
        summary = metadata.get('summary', {})
        shown, used = render_output(raw, code, summary, lambda text: filter_text(text, 'pytest'))
        print(shown, end='' if shown.endswith('\n') else '\n')
        print('Original pytest exit:', code, 'RTK filtered:', used)
        print('Original counts:', json.dumps(summary, ensure_ascii=False))
        print('Raw log:', run/'pytest.log')
        return code
    if not 1 <= args.count <= 100:
        parser.error('--count must be between 1 and 100.')
    result = subprocess.run(['git','log','--oneline',f'-{args.count}','--','.'],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    raw = result.stdout+result.stderr
    shown = raw
    if result.returncode == 0:
        try:
            shown = filter_text(raw, 'git-log')
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    print(shown, end='' if shown.endswith('\n') else '\n')
    print(f'Output bytes: {len(raw.encode("utf-8"))} -> {len(shown.encode("utf-8"))}; raw exit={result.returncode}')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
