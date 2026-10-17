"""Publish a complete directory, with recoverable directory renames."""
from contextlib import contextmanager
from pathlib import Path
import hashlib,json,os,shutil,tempfile,uuid


def _digest(directory):
    result={}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):
            raise ValueError('Export cases must not contain symbolic links or junctions.')
        if path.is_file():
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            result[path.relative_to(directory).as_posix()]=digest.hexdigest()
        elif path.is_dir():result[path.relative_to(directory).as_posix()+'/']='directory'
        else:raise ValueError('Unsupported export case entry: '+str(path))
    return result


def _atomic_json(path,values):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name);json.dump(values,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


@contextmanager
def _lock(path):
    with path.open('a+b') as stream:
        stream.seek(0,2)
        if stream.tell()==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc:raise ValueError('Another export is using this case.') from exc
            try:yield
            finally:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc:raise ValueError('Another export is using this case.') from exc
            try:yield
            finally:fcntl.flock(stream,fcntl.LOCK_UN)


def _owned_paths(target,journal):
    record=json.loads(journal.read_text(encoding='utf-8'))
    token=record.get('token','')
    if record.get('version')!=1 or not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Invalid publication journal; existing case was preserved.')
    prefix='.'+target.name+'.publish-'+token
    stage=target.parent/(prefix+'.stage');backup=target.parent/(prefix+'.backup')
    if record.get('target')!=target.name or type(record.get('old_exists')) is not bool:
        raise ValueError('Publication journal target mismatch; existing case was preserved.')
    for path in (stage,backup):
        if path.parent.resolve()!=target.parent or path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):
            raise ValueError('Unsafe publication recovery path; existing case was preserved.')
    return record,stage,backup


def _recover(target,journal):
    if not journal.exists():return
    record,stage,backup=_owned_paths(target,journal)
    if not target.exists() and backup.is_dir():
        os.replace(backup,target)
    elif target.is_dir() and backup.is_dir():
        if stage.exists() or record.get('new_digest')!=_digest(target):
            raise ValueError('Ambiguous interrupted publication; target and backup were preserved.')
        # A completed generation and its previous generation are both retained.
    elif target.is_dir() and not backup.exists():
        if not record['old_exists'] and not stage.exists() and record.get('new_digest')!=_digest(target):
            raise ValueError('Interrupted publication differs from its journal; case was preserved.')
    elif not target.exists() and not backup.exists() and not record['old_exists']:
        pass
    else:
        raise ValueError('Interrupted publication cannot be recovered automatically; all copies were preserved.')
    if stage.exists():_discard_stage(stage,target)
    journal.unlink()


def _discard_stage(stage,target):
    # Only this transaction's same-parent scratch directory may be removed.
    prefix='.'+target.name+'.publish-'
    token=stage.name[len(prefix):-len('.stage')]
    if (not stage.name.startswith(prefix) or not stage.name.endswith('.stage')
            or len(token)!=32 or any(c not in '0123456789abcdef' for c in token)
            or stage.is_symlink() or (hasattr(stage,'is_junction') and stage.is_junction())
            or stage.resolve().parent!=target.parent):
        raise ValueError('Unsafe scratch cleanup path; all directories were preserved.')
    shutil.rmtree(stage.resolve())


@contextmanager
def staged_case(directory):
    """Yield an isolated case. Old generations are retained as sibling backups.

    Flat filenames remain compatible. Directory renames have a brief absence
    window, rather than a mixed generation. A crash in that window is recovered
    on the next export; no power-loss durability guarantee is claimed.
    """
    raw=Path(directory).absolute()
    if raw.is_symlink() or (hasattr(raw,'is_junction') and raw.is_junction()):raise ValueError('Case directory must not be a link.')
    target=raw.resolve()
    if target==target.parent:raise ValueError('A filesystem root cannot be an export case.')
    target.parent.mkdir(parents=True,exist_ok=True)
    journal=target.parent/('.'+target.name+'.publish.json')
    lock=target.parent/('.'+target.name+'.publish.lock')
    if lock.is_symlink():raise ValueError('Publication lock must not be a link.')
    with _lock(lock):
        _recover(target,journal)
        if target.exists() and not target.is_dir():raise ValueError('Export case must be a directory.')
        token=uuid.uuid4().hex;prefix='.'+target.name+'.publish-'+token
        stage=target.parent/(prefix+'.stage');backup=target.parent/(prefix+'.backup')
        old_exists=target.exists();old_digest=_digest(target) if old_exists else None
        record={'version':1,'token':token,'target':target.name,'old_exists':old_exists,'new_digest':None}
        try:
            _atomic_json(journal,record)
            if old_exists:
                shutil.copytree(target,stage,symlinks=True)
                if _digest(stage)!=old_digest or _digest(target)!=old_digest:raise ValueError('Existing case changed while preparing export.')
            else:stage.mkdir()
            yield stage
            if old_exists and _digest(target)!=old_digest:raise ValueError('Existing case changed during export; no output was replaced.')
            if not old_exists and target.exists():raise ValueError('Case appeared during export; no output was replaced.')
            record['new_digest']=_digest(stage);_atomic_json(journal,record)
            if old_exists:os.replace(target,backup)
            os.replace(stage,target)
            if _digest(target)!=record['new_digest']:raise ValueError('Published case verification failed; backup was preserved.')
            journal.unlink()
        except BaseException:
            # Restore the old case if installation failed after moving it away.
            if not target.exists() and backup.exists():
                try:os.replace(backup,target)
                except OSError:
                    raise OSError('Case installation and rollback failed. Recovery journal and backup: '+str(journal))
            if backup.exists() and target.exists():
                # If the new generation is already installed, retain journal and
                # backup for verification/recovery instead of guessing rollback.
                raise
            if stage.exists():_discard_stage(stage,target)
            journal.unlink(missing_ok=True)
            raise


def publish_case_files(directory,contents):
    """contents is a validated mapping of simple relative paths to bytes."""
    _validate_payloads(contents)
    with staged_case(directory) as stage:
        _write_case_files(stage,contents)


def _validate_payloads(contents):
    names=set()
    for name,data in contents.items():
        relative=Path(name)
        key=relative.as_posix().casefold()
        if relative.anchor or '..' in relative.parts or not relative.parts or any(':' in part for part in relative.parts) or not isinstance(data,bytes) or key in names:raise ValueError('Invalid or duplicate case output payload.')
        names.add(key)


def _write_case_files(directory,contents):
    """Internal writer for an already isolated work area, never a published case."""
    _validate_payloads(contents)
    for name,data in contents.items():
        path=Path(directory)/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
