from pathlib import Path
import uuid
import pytest
from blade_designer.fileio.preview_retention import PreviewJobRetention,FILES


def job(root):
    path=root/uuid.uuid4().hex;path.mkdir(parents=True)
    for name in FILES:(path/name).write_text('private',encoding='utf-8')
    return path


def test_only_recent_completed_owned_jobs_are_retained_and_active_job_is_untouched(tmp_path):
    root=tmp_path/'preview';retention=PreviewJobRetention(root);old=job(root)
    paths=[]
    for _ in range(9):
        path=job(root);paths.append(path);retention.register(path);retention.finished(path,{'overall':'PASS'})
    active=job(root);retention.register(active)
    assert [p.exists() for p in paths]==[False]*4+[True]*5
    assert active.exists() and old.exists()
    retention.trim(dispose=True)
    assert all(not p.exists() for p in paths) and active.exists() and old.exists()


def test_diagnostic_keep_jobs_option_preserves_all_registered_files(tmp_path):
    retention=PreviewJobRetention(tmp_path,keep_jobs=True,limit=0);path=job(tmp_path)
    retention.register(path);retention.finished(path,{'overall':'PASS'});retention.trim(dispose=True)
    assert set(p.name for p in path.iterdir())==FILES


@pytest.mark.parametrize('damage',['outside','invalid_name','not_registered'])
def test_unowned_paths_are_never_removed(tmp_path,damage):
    root=tmp_path/'preview';root.mkdir();retention=PreviewJobRetention(root,limit=0)
    path=job(tmp_path if damage=='outside' else root)
    if damage=='invalid_name':
        target=root/'user-export';path.rename(target);path=target
    if damage=='not_registered':retention.finished(path,{'overall':'PASS'})
    else:
        with pytest.raises(ValueError):retention.register(path)
    retention.trim(dispose=True);assert set(p.name for p in path.iterdir())==FILES


def test_unknown_file_preserves_entire_job_without_partial_deletion(tmp_path):
    retention=PreviewJobRetention(tmp_path,limit=0);path=job(tmp_path);retention.register(path)
    (path/'user.txt').write_text('preserve',encoding='utf-8')
    retention.finished(path,{'overall':'PASS'})
    assert set(p.name for p in path.iterdir())==FILES|{'user.txt'} and retention.warnings


def test_replaced_directory_identity_is_not_authorized(tmp_path):
    retention=PreviewJobRetention(tmp_path,limit=0);path=job(tmp_path);retention.register(path)
    path.rename(tmp_path/'previous');path.mkdir()
    (path/'request.json').write_text('replacement',encoding='utf-8')
    retention.finished(path,{'overall':'PASS'})
    assert (path/'request.json').read_text()=='replacement' and retention.warnings


@pytest.mark.parametrize('status',['NOT_CONFIRMED','NOT_REQUESTED','DIRECT_PROCESS_KILL_REQUESTED'])
def test_unconfirmed_process_tree_keeps_job_even_on_disposal(tmp_path,status):
    retention=PreviewJobRetention(tmp_path,limit=0);path=job(tmp_path);retention.register(path)
    retention.finished(path,{'overall':'FAIL','cancelled':True,'termination_status':status})
    retention.trim(dispose=True);assert path.exists() and set(p.name for p in path.iterdir())==FILES


def test_confirmed_stopped_cancel_can_be_cleaned(tmp_path):
    retention=PreviewJobRetention(tmp_path,limit=0);path=job(tmp_path);retention.register(path)
    retention.finished(path,{'overall':'FAIL','cancelled':True,'termination_status':'PROCESS_TREE_STOPPED'})
    assert not path.exists()


def test_unlink_failure_is_reported_and_never_recurses(tmp_path,monkeypatch):
    retention=PreviewJobRetention(tmp_path,limit=0);path=job(tmp_path);retention.register(path)
    def fail(*args,**kwargs):raise PermissionError('held by another process')
    monkeypatch.setattr(Path,'unlink',fail);retention.finished(path,{'overall':'PASS'})
    assert set(p.name for p in path.iterdir())==FILES and 'held by another process' in retention.warnings[-1]


@pytest.mark.parametrize('link_location',['root','job','file'])
def test_reparse_or_symlink_is_rejected_before_any_deletion(tmp_path,monkeypatch,link_location):
    from types import SimpleNamespace
    import stat
    root=tmp_path/'preview';path=job(root);retention=PreviewJobRetention(root,limit=0);retention.register(path)
    target={'root':root,'job':path,'file':path/'payload.json'}[link_location]
    original=Path.lstat
    def fake(candidate,*args,**kwargs):
        info=original(candidate,*args,**kwargs)
        if candidate==target:return SimpleNamespace(st_mode=info.st_mode,st_file_attributes=getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024),st_dev=info.st_dev,st_ino=info.st_ino)
        return info
    monkeypatch.setattr(Path,'lstat',fake);retention.finished(path,{'overall':'PASS'})
    assert set(p.name for p in path.iterdir())==FILES and retention.warnings
