"""Project snapshots retain invalid input too, so Undo can recover it."""
from copy import deepcopy
from PySide6.QtGui import QUndoCommand

class ProjectEditCommand(QUndoCommand):
    def __init__(self,window,before,after,before_span,after_span,text="Edit design",*,before_target=None,after_target=None):
        super().__init__(text);self.window=window
        self.before=deepcopy(before);self.after=deepcopy(after)
        self.before_span=before_span;self.after_span=after_span;self._first=True
        self.before_target=before_target;self.after_target=after_target

    def undo(self):self.window._restore_design(self.before,self.before_span,self.before_target)

    def redo(self):
        if self._first:self._first=False
        else:self.window._restore_design(self.after,self.after_span,self.after_target)
