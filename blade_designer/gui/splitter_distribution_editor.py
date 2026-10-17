"""LE-to-TE controls; hold the LE value fixed when any visible point is edited."""
from copy import deepcopy
import numpy as np
from .control_point_editor import ControlPointEditor
from ..geometry.splitter import splitter_edit_points
from ..models.parameters import DistributionPoint
from ..models.validation import validate_control_points,ValidationLevel


class SplitterControlPointEditor(ControlPointEditor):
    def __init__(self,*args,**kwargs):
        self.start_fraction=0.;self._source_points=[];self._initial_visible=[];self._virtual=False
        super().__init__(*args,**kwargs)

    def set_start_fraction(self,start):
        if start==self.start_fraction:return
        points=self.get_points();self.start_fraction=start;self.set_points(points)

    def set_points(self,points):
        self._source_points=deepcopy(points)
        self._virtual=not any(p.m_norm==self.start_fraction for p in points)
        try:visible=splitter_edit_points(points,self.start_fraction)
        except (ValueError,TypeError,ArithmeticError):
            # Keep invalid source data intact; do not invent a boundary value.
            visible=deepcopy([p for p in points if p.m_norm>=self.start_fraction]);self._virtual=False
        self._initial_visible=deepcopy(visible)
        super().set_points(visible)
        for row in range(len(visible)):
            self.table.cellWidget(row,0).setRange(self.start_fraction,1.)
            for col in (0,1):self.table.cellWidget(row,col).setKeyboardTracking(False)

    def get_points(self):
        if self._points==self._initial_visible:return deepcopy(self._source_points)
        upstream=[p for p in self._source_points if not p.m_norm>=self.start_fraction]
        active=self._points[1:] if self._virtual else self._points
        return deepcopy(upstream+active)

    def _show_validation(self):
        errors=[i.message for i in validate_control_points(self.get_points(),self.kind) if i.level==ValidationLevel.ERROR]
        self.message.setText('; '.join(errors));self.message.setStyleSheet('color: #b03030;')

    def _cell_changed(self,row,column,value):
        if column==0 and 0<row<len(self._points)-1:
            lo,hi=self._points[row-1].m_norm,self._points[row+1].m_norm
            margin=min(1e-6,(hi-lo)/4);value=float(np.clip(value,lo+margin,hi-margin))
            box=self.table.cellWidget(row,0);box.blockSignals(True);box.setValue(value);box.blockSignals(False)
        # The visible LE becomes a real endpoint on the first edit so hidden
        # upstream controls cannot move it while a downstream point changes.
        self._virtual=False
        setattr(self._points[row],'m_blade_norm' if column==0 else 'value',value)
        self.handles.set_points(self._points);self._show_validation();self.pointsChanged.emit()

    def move_point(self,index,m_blade_norm,value):
        points=self._points
        if index==0:m_blade_norm=points[0].m_norm
        elif index==len(points)-1:m_blade_norm=1.
        else:
            lo,hi=points[index-1].m_norm,points[index+1].m_norm
            margin=min(1e-6,(hi-lo)/4)
            m_blade_norm=float(np.clip(m_blade_norm,lo+margin,hi-margin))
        value=float(np.clip(value,-84.999999,84.999999)) if self.kind=='blade_angle' else max(0.,float(value))
        self._virtual=False
        points[index]=DistributionPoint(m_blade_norm,value)
        for col,v in enumerate((m_blade_norm,value)):
            box=self.table.cellWidget(index,col);box.blockSignals(True);box.setValue(v);box.blockSignals(False)
        self.handles.set_points(points);self._show_validation();self.pointsChanged.emit()

    def add_point(self):
        if len(self._points)<2:return
        if any(i.level==ValidationLevel.ERROR for i in validate_control_points(self.get_points(),self.kind)):
            self.message.setText('Correct invalid controls or copy the main blade again.');return
        index=int(np.argmax(np.diff([p.m_norm for p in self._points])))
        self._virtual=False
        a,b=self._points[index:index+2];position=(a.m_norm+b.m_norm)/2
        self._points.insert(index+1,DistributionPoint(position,(a.value+b.value)/2))
        self.set_points(self.get_points());self.table.selectRow(index+1)
        self.pointsChanged.emit();self.editFinished.emit()

    def delete_point(self):
        row=self.table.currentRow()
        if not 0<row<len(self._points)-1:return
        self._virtual=False
        del self._points[row];self.set_points(self.get_points())
        self.pointsChanged.emit();self.editFinished.emit()
