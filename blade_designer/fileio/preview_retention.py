"""Retention only for private jobs registered by the creating controller."""
from pathlib import Path
import re
import stat


FILES=frozenset(('snapshot.json','request.json','payload.json','payload.part.json',
                 'result.json','result.part.json','process.log','error.log'))


def _plain(path,directory=False):
    info=path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):
        raise ValueError('Preview retention refuses links or reparse points.')
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError('Unexpected preview retention file type.')
    return info.st_dev,info.st_ino


class PreviewJobRetention:
    def __init__(self,root,keep_jobs=False,limit=5):
        self.root=Path(root).absolute();self.keep_jobs=keep_jobs;self.limit=limit
        self._owned={};self._finished=[];self.warnings=[]

    def _identity(self,path):
        path=Path(path).absolute()
        if path.parent!=self.root or not re.fullmatch('[0-9a-f]{32}',path.name):
            raise ValueError('Preview retention path outside owned job root.')
        # Check the lexical path before resolving: a junction may stay inside
        # the same workspace but still lead into an unrelated directory.
        for parent in (self.root,*self.root.parents):_plain(parent,directory=True)
        return _plain(path,directory=True)

    def register(self,path):
        path=Path(path).absolute();self._owned[path]=self._identity(path)

    def finished(self,path,report):
        path=Path(path).absolute()
        if path not in self._owned:return
        if report.get('cancelled') and report.get('termination_status')!='PROCESS_TREE_STOPPED':return
        if path not in self._finished:self._finished.append(path)
        self.trim()

    def trim(self,dispose=False):
        if self.keep_jobs:return
        count=len(self._finished) if dispose else max(0,len(self._finished)-self.limit)
        for path in self._finished[:count]:
            try:
                if self._identity(path)!=self._owned[path]:raise ValueError('Owned preview directory was replaced.')
                entries=list(path.iterdir())
                if any(entry.name not in FILES for entry in entries):raise ValueError('Unknown files in private preview job; preserved.')
                for entry in entries:_plain(entry)
                # No recursive removal, and no filesystem mutation until all
                # paths, identities and file types have been checked above.
                for entry in entries:entry.unlink()
                path.rmdir()
            except (OSError,ValueError) as exc:
                self.warnings.append(str(exc));self.warnings=self.warnings[-5:]
            else:self._owned.pop(path,None)
            self._finished.remove(path)
