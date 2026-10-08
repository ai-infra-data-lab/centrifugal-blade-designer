"""Persistent draggable endpoints, projected only to their corresponding wall."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from ..geometry.blade_edge import edge_endpoints,project_to_wall

class BladeEdgeHandles(pg.GraphItem):
    def __init__(self,context,key,side,color):
        super().__init__();self.context=context;self.key=key;self.side=side
        self.wall_index=None;self.walls=None;self.color=color
        self.label=pg.TextItem(("IMP" if key=="impeller_edges" else "DIF")+" "+("LE" if side=="leading_edge" else "TE"),color=color,anchor=(.5,1))
        name=("Impeller" if key=="impeller_edges" else "Diffuser")+" "+("LE" if side=="leading_edge" else "TE")
        self.legend_item=context.plot.plot([],[],pen=pg.mkPen(color,width=2.5),symbol="o",symbolBrush=color,name=name)
        context.plot.addItem(self.label,ignoreBounds=True)
        context.plot.addItem(self)
        self.setZValue(20)

    def update_edge(self,edges,hub,shroud):
        self.walls=(hub,shroud)
        points=edge_endpoints(getattr(edges,self.side),hub,shroud)
        self.setData(pos=points,adj=np.array([[0,1]]),data=np.arange(2),size=13,
            symbol="o",symbolBrush=self.color,pen=pg.mkPen(self.color,width=2.5),pxMode=True)
        self.label.setPos(*np.mean(points,axis=0))

    def hoverEvent(self,event):
        if not event.isExit() and len(self.scatter.pointsAt(event.pos())):
            event.acceptDrags(Qt.MouseButton.LeftButton)

    def mouseDragEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or self.walls is None:event.ignore();return
        if event.isStart():
            points=self.scatter.pointsAt(event.buttonDownPos())
            if not points:event.ignore();return
            self.wall_index=int(points[0].data());self.context.edgeDragStarted.emit()
        if self.wall_index is None:event.ignore();return
        wall="hub" if self.wall_index==0 else "shroud"
        value,_=project_to_wall(self.walls[self.wall_index],[event.pos().x(),event.pos().y()])
        self.context.endpointMoved.emit(self.key,self.side,wall,value)
        if event.isFinish():
            self.wall_index=None;self.context.edgeDragFinished.emit()
        event.accept()
