"""Install a pinned Windows RTK OSS binary inside ignored project artifacts."""
from pathlib import Path
import hashlib
import io
import json
import platform
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def verified_members(archive, release):
    if hashlib.sha256(archive).hexdigest() != release['archive_sha256']:
        raise ValueError('RTK archive checksum mismatch; nothing installed.')
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        executable = bundle.read('rtk.exe')
        license_text = bundle.read('LICENSE')
    if hashlib.sha256(executable).hexdigest() != release['exe_sha256']:
        raise ValueError('RTK executable checksum mismatch; nothing installed.')
    return executable, license_text


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    if platform.system() != 'Windows' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('This pinned installer supports Windows x64 only.')
    release = json.loads((ROOT/'tools/rtk-release.json').read_text(encoding='utf-8'))
    folder = ROOT/'artifacts/devtools/rtk'
    executable = folder/'rtk.exe'
    if executable.exists():
        if hashlib.sha256(executable.read_bytes()).hexdigest() != release['exe_sha256']:
            raise SystemExit('An unexpected RTK binary already exists; not overwritten.')
        print('Pinned RTK already installed:', executable)
        return
    with urllib.request.urlopen(release['url'], timeout=60) as response:
        archive = response.read()
    binary, license_text = verified_members(archive, release)
    folder.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(binary)
    (folder/'LICENSE').write_bytes(license_text)
    print('Installed checksum-verified RTK OSS', release['version'], executable)


if __name__ == '__main__':
    main()
