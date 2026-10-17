"""Additional OS-level and cancellation checks; no geometry reference changes."""
from pathlib import Path
import ctypes,errno,os
import pytest
from blade_designer.fileio.case_publish import publish_case_files,staged_case


def case(tmp_path):
    target=tmp_path/'case';target.mkdir()
    (target/'main.step').write_bytes(b'old main')
    (target/'splitter.step').write_bytes(b'old splitter')
    return target


def values(target):return {p.name:p.read_bytes() for p in target.iterdir()}


@pytest.mark.skipif(os.name!='nt',reason='Native Windows handle-sharing test')
def test_actual_windows_directory_handle_lock_preserves_case(tmp_path):
    from ctypes import wintypes
    target=case(tmp_path);before=values(target)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    create.restype=wintypes.HANDLE
    close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
    # Deliberately deny FILE_SHARE_DELETE on the directory itself.
    handle=create(str(target),0x80000000,3,None,3,0x02000000,None)
    assert handle!=ctypes.c_void_p(-1).value,ctypes.get_last_error()
    try:
        with pytest.raises(PermissionError):publish_case_files(target,{'main.step':b'new main'})
        assert values(target)==before
    finally:assert close(handle)
    publish_case_files(target,{'main.step':b'new main'})
    assert (target/'main.step').read_bytes()==b'new main'


def test_cancellation_during_preparation_preserves_old_case(tmp_path):
    target=case(tmp_path);before=values(target)
    with pytest.raises(KeyboardInterrupt):
        with staged_case(target) as stage:
            (stage/'main.step').write_bytes(b'candidate')
            raise KeyboardInterrupt('injected cancellation')
    assert values(target)==before


def test_disk_full_after_first_file_changes_no_published_files(tmp_path,monkeypatch):
    target=case(tmp_path);before=values(target);original=Path.open
    def fail_second(path,mode='r',*args,**kwargs):
        if 'w' in mode and path.name=='splitter.step' and any(part.endswith('.stage') for part in path.parts):
            raise OSError(errno.ENOSPC,'injected disk full')
        return original(path,mode,*args,**kwargs)
    monkeypatch.setattr(Path,'open',fail_second)
    with pytest.raises(OSError,match='disk full'):
        publish_case_files(target,{'main.step':b'new main','splitter.step':b'new splitter'})
    assert values(target)==before
