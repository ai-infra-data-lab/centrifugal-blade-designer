"""Software-rendered orthographic wireframe; works without VTK/OpenGL."""
from copy import deepcopy
import numpy as np
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QPainter,QPen,QColor,QPolygonF
from PySide6.QtWidgets import QWidget,QCheckBox,QHBoxLayout,QVBoxLayout
from ..geometry.wireframe import build_spanwise_wireframe


class Preview3D(QWidget):
    def __init__(self):
        super().__init__();self.setMinimumSize(320,180)
        self.camera_position={"azimuth":-45.,"elevation":25.,"scale":160.,"center":np.zeros(3),"pan":np.zeros(2)}
        self.lines={};self.spanwise_lines=[];self._last=None
        self.visibility_controls={}
        layout=QVBoxLayout(self);row=QHBoxLayout();layout.addLayout(row);layout.addStretch()
        for key,label in (("profiles","Show Profiles"),("spanwise","Show Spanwise Lines"),("hub","Show Hub Curve"),("shroud","Show Shroud Curve")):
            box=QCheckBox(label);box.setChecked(True);box.setStyleSheet("color: #d1dae7;")
            box.toggled.connect(self.update);row.addWidget(box);self.visibility_controls[key]=box
        row.addStretch()


    def update_geometry(self,geometry):
        spanwise=build_spanwise_wireframe(geometry.sections)
        camera=deepcopy(self.camera_position)
        lines={"Hub":(np.column_stack((geometry.hub.r,np.zeros_like(geometry.hub.r),geometry.hub.z)),"#56d9e0"),
               "Shroud":(np.column_stack((geometry.shroud.r,np.zeros_like(geometry.shroud.r),geometry.shroud.z)),"#eead72")}
        for section in geometry.sections:
            label="Hub" if section.span==0 else "Tip" if section.span==1 else f"Span {section.span:.6g}"
            for name,color in (("le","#e5c76b"),("ps","#56d9e0"),("te","#eead72"),("ss","#f6948c"),("camber","#aab4c5")):
                lines[f"{label} {name}"]=(getattr(section,"master_"+name if name!="camber" else name).xyz,color)
        for line in spanwise:
            lines[f"Spanwise {line.segment} {line.segment_index}"]=(line.xyz,"#496b8e")
        self.lines=lines;self.spanwise_lines=spanwise;self.camera_position=camera;self.update()

    def visible_lines(self):
        # Draw span grid first so the bright profile outlines remain visible.
        ordered=sorted(self.lines.items(),key=lambda item:not item[0].startswith("Spanwise "))
        for name,data in ordered:
            category="hub" if name=="Hub" else "shroud" if name=="Shroud" else "spanwise" if name.startswith("Spanwise ") else "profiles"
            if self.visibility_controls[category].isChecked():yield data


    def fit_view(self):
        if not self.lines:return
        xyz=np.concatenate([points for points,color in self.lines.values()])
        self.camera_position["center"]=(xyz.min(axis=0)+xyz.max(axis=0))/2
        a,e=np.deg2rad([self.camera_position["azimuth"],self.camera_position["elevation"]])
        right=np.array([-np.sin(a),np.cos(a),0]);up=np.array([-np.cos(a)*np.sin(e),-np.sin(a)*np.sin(e),np.cos(e)])
        projected=np.array([np.ptp(xyz@right),np.ptp(xyz@up)])
        factor=min(max(self.width(),1)/max(projected[0],1e-6),max(self.height()-80,1)/max(projected[1],1e-6))/1.2
        self.camera_position["scale"]=max(min(self.width(),self.height())/(2*factor),1e-6)
        self.camera_position["pan"]=np.zeros(2);self.update()

    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor("#101c2b"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        camera=self.camera_position;a,e=np.deg2rad([camera["azimuth"],camera["elevation"]])
        right=np.array([-np.sin(a),np.cos(a),0]);up=np.array([-np.cos(a)*np.sin(e),-np.sin(a)*np.sin(e),np.cos(e)])
        factor=min(self.width(),self.height())/(2*camera["scale"])
        painter.save();painter.setClipRect(0,60,self.width(),max(0,self.height()-85))
        for points,color in self.visible_lines():
            relative=points-camera["center"]
            x=(relative@right+camera["pan"][0])*factor+self.width()/2
            y=-(relative@up+camera["pan"][1])*factor+(self.height()+60)/2
            painter.setPen(QPen(QColor(color),1.4))
            painter.drawPolyline(QPolygonF([QPointF(float(xx),float(yy)) for xx,yy in zip(x,y)]))
        painter.restore();painter.setPen(QColor("#d1dae7"))
        painter.drawText(12,52,"3D • Left drag: rotate  |  Right drag: pan  |  Wheel: zoom")
        painter.drawText(12,self.height()-14,"XYZ [mm] • Z rotation axis • profile / spanwise wireframe")
        painter.end()

    def mousePressEvent(self,event):self._last=event.position();event.accept()

    def mouseMoveEvent(self,event):
        if self._last is None:return
        delta=event.position()-self._last;self._last=event.position()
        camera=self.camera_position
        if event.buttons() & Qt.MouseButton.LeftButton:
            camera["azimuth"]+=delta.x()*.5;camera["elevation"]=float(np.clip(camera["elevation"]+delta.y()*.5,-89,89))
        elif event.buttons() & Qt.MouseButton.RightButton:
            factor=2*camera["scale"]/max(1,min(self.width(),self.height()))
            camera["pan"]+=np.array([delta.x(),-delta.y()])*factor
        self.update();event.accept()

    def mouseReleaseEvent(self,event):self._last=None;event.accept()

    def wheelEvent(self,event):
        self.camera_position["scale"]=float(np.clip(self.camera_position["scale"]*np.exp(-event.angleDelta().y()/1200),1e-6,1e12))
        self.update();event.accept()
