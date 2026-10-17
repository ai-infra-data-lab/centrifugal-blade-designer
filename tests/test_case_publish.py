from pathlib import Path
import json,os,subprocess,sys
import pytest
from blade_designer.fileio import case_publish as cp


def case_files(folder):
    return {p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def old_case(tmp_path):
    target=tmp_path/'case';target.mkdir()
    (target/'hub.curve').write_bytes(b'old hub')
    (target/'shroud.curve').write_bytes(b'old shroud')
    (target/'user.txt').write_bytes(b'keep user data')
    (target/'notes').mkdir();(target/'notes'/'settings.json').write_bytes(b'keep settings')
    return target


def test_complete_generation_preserves_unmanaged_files_and_keeps_backup(tmp_path):
    target=old_case(tmp_path);before=case_files(target)
    cp.publish_case_files(target,{'hub.curve':b'new hub','shroud.curve':b'new shroud'})
    assert case_files(target)=={**before,'hub.curve':b'new hub','shroud.curve':b'new shroud'}
    backups=list(tmp_path.glob('.case.publish-*.backup'))
    assert len(backups)==1 and case_files(backups[0])==before
    assert not list(tmp_path.glob('*.stage'))
    assert not (tmp_path/'.case.publish.json').exists()


@pytest.mark.parametrize('destination',['journal','prepared_journal','backup','target'])
def test_each_publication_failure_restores_old_generation(tmp_path,monkeypatch,destination):
    target=old_case(tmp_path);before=case_files(target)
    original=cp.os.replace;failed=False;journal_calls=0
    def fail(source,dest):
        nonlocal failed,journal_calls
        dest=Path(dest)
        if dest.name.endswith('.publish.json'):journal_calls+=1
        selected=(dest.name.endswith('.publish.json') and journal_calls==(2 if destination=='prepared_journal' else 1)) if destination in ('journal','prepared_journal') else dest.name.endswith('.backup') if destination=='backup' else dest==target
        if selected and not failed:failed=True;raise PermissionError('injected locked destination')
        return original(source,dest)
    monkeypatch.setattr(cp.os,'replace',fail)
    with pytest.raises(PermissionError):cp.publish_case_files(target,{'hub.curve':b'new'})
    assert failed and case_files(target)==before
    assert not list(tmp_path.glob('.case.publish-*.stage'))


def test_body_failure_changes_no_old_files_or_new_case(tmp_path):
    target=old_case(tmp_path);before=case_files(target)
    for folder in (target,tmp_path/'new'):
        with pytest.raises(OSError,match='disk error'):
            with cp.staged_case(folder) as stage:
                (stage/'hub.curve').write_bytes(b'partial')
                raise OSError('injected disk error')
    assert case_files(target)==before and not (tmp_path/'new').exists()


def test_concurrent_external_edit_is_preserved(tmp_path):
    target=old_case(tmp_path)
    with pytest.raises(ValueError,match='changed during'):
        with cp.staged_case(target) as stage:
            (stage/'hub.curve').write_bytes(b'new')
            (target/'user.txt').write_bytes(b'external edit')
    assert (target/'hub.curve').read_bytes()==b'old hub'
    assert (target/'user.txt').read_bytes()==b'external edit'


@pytest.mark.parametrize('when',['prepared','old_moved','new_installed'])
def test_process_crash_is_recoverable_without_mixed_case(tmp_path,when):
    target=old_case(tmp_path)
    script='''
import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from blade_designer.fileio import case_publish as cp
target=Path(sys.argv[2]);when=sys.argv[3];original=cp.os.replace
def crash(source,destination):
    original(source,destination)
    destination=Path(destination)
    if ((when=='prepared' and destination.name.endswith('.publish.json') and Path(source).name.startswith('tmp'))
        or (when=='old_moved' and destination.name.endswith('.backup'))
        or (when=='new_installed' and destination==target)):
        if when!='prepared' or 'new_digest' in destination.read_text() and 'null' not in destination.read_text():os._exit(23)
cp.os.replace=crash
cp.publish_case_files(target,{'hub.curve':b'first new hub','shroud.curve':b'first new shroud'})
'''
    result=subprocess.run([sys.executable,'-c',script,str(Path(cp.__file__).parent),str(target),when],timeout=30)
    assert result.returncode==23
    cp.publish_case_files(target,{'extra.txt':b'next generation'})
    prefix=b'first new' if when=='new_installed' else b'old'
    assert (target/'hub.curve').read_bytes()==prefix+b' hub'
    assert (target/'shroud.curve').read_bytes()==prefix+b' shroud'
    assert (target/'user.txt').read_bytes()==b'keep user data'
    assert not (tmp_path/'.case.publish.json').exists()


def test_failed_rollback_keeps_journal_and_recoverable_backup(tmp_path,monkeypatch):
    target=old_case(tmp_path);before=case_files(target);original=cp.os.replace
    def fail_install_and_rollback(source,dest):
        if Path(dest)==target:raise PermissionError('injected persistent lock')
        return original(source,dest)
    monkeypatch.setattr(cp.os,'replace',fail_install_and_rollback)
    with pytest.raises(OSError,match='rollback failed'):cp.publish_case_files(target,{'hub.curve':b'new'})
    assert not target.exists() and (tmp_path/'.case.publish.json').exists()
    monkeypatch.setattr(cp.os,'replace',original)
    with cp.staged_case(target) as stage:
        assert case_files(stage)==before
    assert case_files(target)==before


def test_invalid_payload_does_not_create_output(tmp_path):
    for name in ('../outside',str(tmp_path/'absolute'),'C:relative','/rooted','file:stream'):
        with pytest.raises(ValueError):cp.publish_case_files(tmp_path/'case',{name:b'x'})
    assert not list(tmp_path.iterdir())


def test_os_lock_prevents_parallel_export(tmp_path):
    target=old_case(tmp_path);before=case_files(target)
    with cp.staged_case(target):
        with pytest.raises(ValueError,match='Another export'):cp.publish_case_files(target,{'hub.curve':b'other'})
    assert case_files(target)==before


def test_new_case_installation_failure_creates_no_case(tmp_path,monkeypatch):
    target=tmp_path/'case';original=cp.os.replace
    def fail(source,destination):
        if Path(destination)==target:raise PermissionError('injected new installation lock')
        return original(source,destination)
    monkeypatch.setattr(cp.os,'replace',fail)
    with pytest.raises(PermissionError):cp.publish_case_files(target,{'hub.curve':b'new'})
    assert not target.exists() and not list(tmp_path.glob('.case.publish-*.stage'))


def test_malformed_journal_and_unsafe_cleanup_preserve_user_directories(tmp_path):
    target=old_case(tmp_path);before=case_files(target)
    foreign=tmp_path/'user data';foreign.mkdir();(foreign/'keep').write_bytes(b'original')
    journal=tmp_path/'.case.publish.json'
    journal.write_text(json.dumps({'version':1,'token':'../user data','target':'case','old_exists':True}))
    with pytest.raises(ValueError,match='journal'):cp.publish_case_files(target,{'hub.curve':b'new'})
    with pytest.raises(ValueError,match='cleanup'):cp._discard_stage(foreign,target)
    assert case_files(target)==before and (foreign/'keep').read_bytes()==b'original'


def test_unicode_case_and_nested_output_keep_flat_existing_paths(tmp_path):
    target=tmp_path/'日本語 ケース'
    cp.publish_case_files(target,{'mechanical/blade.step':b'verified bytes'})
    cp.publish_case_files(target,{'mechanical/blade.step':b'next verified bytes','validation/report.json':b'{}'})
    assert (target/'mechanical'/'blade.step').read_bytes()==b'next verified bytes'
    assert (target/'validation'/'report.json').read_bytes()==b'{}'


def test_different_cases_are_not_blocked_by_each_others_lock(tmp_path):
    first=old_case(tmp_path);second=tmp_path/'other'
    with cp.staged_case(first) as stage:
        cp.publish_case_files(second,{'hub.curve':b'other'})
        (stage/'hub.curve').write_bytes(b'first new')
    assert (first/'hub.curve').read_bytes()==b'first new'
    assert (second/'hub.curve').read_bytes()==b'other'


def test_root_and_regular_file_are_not_replaced(tmp_path):
    file=tmp_path/'not a case';file.write_bytes(b'keep')
    with pytest.raises(ValueError,match='directory'):cp.publish_case_files(file,{'hub.curve':b'new'})
    with pytest.raises(ValueError,match='root'):cp.publish_case_files(Path(tmp_path.anchor),{'hub.curve':b'new'})
    assert file.read_bytes()==b'keep'
