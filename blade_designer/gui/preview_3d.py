"""Software-rendered orthographic wireframe; works without VTK/OpenGL."""
from copy import deepcopy
import numpy as np
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QPainter,QPen,QColor,QPolygonF
from PySide6.QtWidgets import QWidget,QCheckBox,QHBoxLayout,QVBoxLayout
from ..geometry.wireframe import build_spanwise_wireframe
from ..geometry.annulus import rotate_xy


class Preview3D(QWidget):
    def __init__(self):
        super().__init__();self.setMinimumSize(320,180)
        self.camera_position={"azimuth":-45.,"elevation":25.,"scale":160.,"center":np.zeros(3),"pan":np.zeros(2)}
        self.lines={};self.spanwise_lines=[];self._last=None
        self.base_lines = {};self.full_annulus = False;self.blade_count = 1
        self.model_label = "3D"
        self.visibility_controls={}
        layout=QVBoxLayout(self);row=QHBoxLayout();layout.addLayout(row);layout.addStretch()
        for key,label in (("profiles","Profiles"),("spanwise","Spanwise"),("hub","Hub"),("shroud","Shroud")):
            box=QCheckBox(label);box.setChecked(True);box.setStyleSheet("color: #d1dae7;")
            box.toggled.connect(self.update);row.addWidget(box);self.visibility_controls[key]=box
        row.addStretch()


    def update_geometry(self,geometry):
        self.model_label = "3D • Impeller"
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
        self.base_lines=lines;self.spanwise_lines=spanwise;self.camera_position=camera;self._rebuild_lines()

    def update_diffuser(self, geometry, walls):
        """Show the existing planar diffuser in XYZ; no invented span geometry."""
        self.model_label = "Diffuser • planar profile in XYZ (Z=0)"
        lines={"Hub": (np.column_stack((walls.hub.r,np.zeros_like(walls.hub.r),walls.hub.z)),"#56d9e0"),
               "Shroud": (np.column_stack((walls.shroud.r,np.zeros_like(walls.shroud.r),walls.shroud.z)),"#eead72")}
        for name,color in (("le","#e5c76b"),("ps","#56d9e0"),("te","#eead72"),("ss","#f6948c"),("camber","#aab4c5")):
            curve=geometry.camber if name=="camber" else getattr(geometry.master_surfaces,name)
            lines[f"Diffuser {name}"]=(np.column_stack((curve.x,curve.y,np.zeros_like(curve.x))),color)
        self.base_lines=lines;self.spanwise_lines=[];self._rebuild_lines()

    def set_full_annulus(self, enabled, blade_count):
        if not isinstance(blade_count, int) or isinstance(blade_count, bool) or blade_count < 1:
            raise ValueError("Blade count must be a positive integer.")
        if self.full_annulus == enabled and self.blade_count == blade_count: return
        self.full_annulus=bool(enabled);self.blade_count=blade_count;self._rebuild_lines()

    def _rebuild_lines(self):
        if not self.full_annulus:
            self.lines=dict(self.base_lines)
        else:
            self.lines={}
            for name,(points,color) in self.base_lines.items():
                # Render-only sampling; design geometry and exports retain all points.
                indices=np.linspace(0,len(points)-1,min(len(points),151),dtype=int)
                points=points[indices]
                for index in range(self.blade_count):
                    x,y=rotate_xy(points[:,0],points[:,1],2*np.pi*index/self.blade_count)
                    self.lines[f"{name} • blade {index+1}"]=(np.column_stack((x,y,points[:,2])),color)
        self.update()

    def visible_lines(self):
        # Draw span grid first so the bright profile outlines remain visible.
        ordered=sorted(self.lines.items(),key=lambda item:not item[0].startswith("Spanwise "))
        for name,data in ordered:
            name=name.split(" • blade ")[0]
            category="hub" if name=="Hub" else "shroud" if name=="Shroud" else "spanwise" if name.startswith("Spanwise ") else "profiles"
            if self.visibility_controls[category].isChecked():yield data


    def fit_view(self):
        if not self.lines:return
        xyz=np.concatenate([points for points,color in self.lines.values()])
        self.camera_position["center"]=(xyz.min(axis=0)+xyz.max(axis=0))/2
        a,e=np.deg2rad([self.camera_position["azimuth"],self.camera_position["elevation"]])
        right=np.array([-np.sin(a),np.cos(a),0]);up=np.array([-np.cos(a)*np.sin(e),-np.sin(a)*np.sin(e),np.cos(e)])
        relative=xyz-self.camera_position["center"]
        projected_center=np.array([(np.min(relative@axis)+np.max(relative@axis))/2 for axis in (right,up)])
        self.camera_position["center"]+=right*projected_center[0]+up*projected_center[1]
        projected=np.array([np.ptp(xyz@right),np.ptp(xyz@up)])
        factor=min(max(self.width(),1)/max(projected[0],1e-6),max(self.height()-85,1)/max(projected[1],1e-6))/1.2
        self.camera_position["scale"]=max(min(self.width(),self.height())/(2*factor),1e-6)
        self.camera_position["pan"]=np.array([0.,12.5/factor]);self.update()

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
        painter.drawText(12,52,self.model_label)
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
