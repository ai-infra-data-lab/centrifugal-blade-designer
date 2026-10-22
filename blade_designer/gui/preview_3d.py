"""Software-rendered revolved walls and blade wireframe, without VTK/OpenGL."""
import numpy as np
from PySide6.QtCore import Qt,QPointF,QTimer
from PySide6.QtGui import QPainter,QPen,QColor,QPolygonF
from PySide6.QtWidgets import QWidget,QCheckBox,QHBoxLayout,QVBoxLayout,QToolButton,QToolTip
from ..geometry.wireframe import build_spanwise_wireframe
from ..geometry.annulus import rotate_xy
from ..geometry.revolved_surface import revolve_wall
from .surface_render import SurfaceFrame,SurfaceRenderQueue


class Preview3D(QWidget):
    _surface_async_threshold=4096
    def __init__(self):
        super().__init__();self.setMinimumSize(320,180)
        self.camera_position={"azimuth":-45.,"elevation":25.,"rotation":np.eye(3),"scale":160.,"center":np.zeros(3),"pan":np.zeros(2)}
        self._plot_top=90
        self.lines={};self.spanwise_lines=[];self._last=None
        self.base_lines = {};self.full_annulus = False;self.blade_count = 1
        self.surfaces = {}
        self._line_blade_counts = {}
        self.model_label = "3D"
        self._reference_mode = False
        self.visibility_controls={}
        layout=QVBoxLayout(self);row=QHBoxLayout();layout.addLayout(row)
        for key,label in (("profiles","Profiles"),("spanwise","Spanwise"),("hub","Hub"),("shroud","Shroud")):
            box=QCheckBox(label);box.setChecked(True);box.setStyleSheet("color: #d1dae7;")
            box.toggled.connect(self.update);row.addWidget(box);self.visibility_controls[key]=box
        box=QCheckBox('Tip');box.setToolTip('翼端の回転包絡面 / Tip envelope');box.setChecked(True);box.setStyleSheet('color: #8deb87;')
        box.toggled.connect(self.update);row.addWidget(box);self.visibility_controls['tip_wall']=box;box.hide()
        row.addStretch()
        box=QCheckBox('Analysis');box.setToolTip('解析用Shroud（紫）／図面用Casing（橙）')
        box.setChecked(True);box.setStyleSheet('color: #d59cfa;');box.toggled.connect(self.update)
        row.insertWidget(row.count()-1,box);self.visibility_controls['analysis_shroud']=box;box.hide()
        views=QHBoxLayout();layout.addLayout(views);layout.addStretch()
        self.view_buttons={}
        for name,label,tip in (("front","正面","+X方向から見る（YZ）"),
                               ("top","上面","+Z方向から見る（XY）"),
                               ("side","側面","+Y方向から見る（XZ）"),
                               ("iso","等角","等角図"),
                               ("fit","全体","向きを維持して全体を表示"),
                               ("reset","リセット","初期方向へ戻して全体を表示")):
            button=QToolButton();button.setText(label);button.setToolTip(tip)
            button.clicked.connect(lambda checked=False,name=name:self.set_view(name))
            views.addWidget(button);self.view_buttons[name]=button
        views.addStretch()
        self.setToolTip("左ドラッグ: 自由回転 / 右ドラッグ: 平行移動 / ホイール: 拡大・縮小")
        self._show_fit=QTimer(self);self._show_fit.setSingleShot(True);self._show_fit.timeout.connect(self.fit_view)
        self._surface_render=SurfaceRenderQueue();self._surface_cache=None;self._cad_mesh_generation=0
        self._surface_poll=QTimer(self);self._surface_poll.setInterval(20)
        self._surface_poll.timeout.connect(self._poll_surface_image)
        self.destroyed.connect(self._surface_render.shutdown)

    def showEvent(self,event):
        super().showEvent(event);self._show_fit.start(0)

    def _view_basis(self):
        """Screen basis with a free rotation, retaining the legacy angle API."""
        camera=self.camera_position;a,e=np.deg2rad([camera["azimuth"],camera["elevation"]])
        right=np.array([-np.sin(a),np.cos(a),0.])
        up=np.array([-np.cos(a)*np.sin(e),-np.sin(a)*np.sin(e),np.cos(e)])
        return camera["rotation"]@np.array([right,up,np.cross(right,up)])

    def set_view(self,name):
        if name=="fit":self.fit_view();return
        angles={"front":(0.,0.),"top":(-90.,90.),"side":(90.,0.),
                "iso":(-45.,np.rad2deg(np.arctan(1/np.sqrt(2)))),"reset":(-45.,25.)}
        azimuth,elevation=angles[name]
        self.camera_position.update(azimuth=azimuth,elevation=elevation,rotation=np.eye(3))
        self._last=None
        self.fit_view();self.update()

    def _trackball_point(self,point):
        radius=max(1.,min(self.width(),self.height()-self._plot_top-25)/2)
        x=(point.x()-self.width()/2)/radius
        y=((self.height()+self._plot_top-25)/2-point.y())/radius
        length=x*x+y*y
        if length>1:
            return np.array([x,y,0.])/np.sqrt(length)
        return np.array([x,y,np.sqrt(max(0.,1-length))])

    def _rotate_trackball(self,previous,current):
        a,b=self._trackball_point(previous),self._trackball_point(current)
        axis=np.cross(a,b);sine=np.linalg.norm(axis);cosine=float(np.clip(a@b,-1.,1.))
        if sine<1e-12:
            if cosine>0:return
            # Opposite rim points still define a valid half turn.
            axis=np.cross(a,np.eye(3)[np.argmin(np.abs(a))]);axis/=np.linalg.norm(axis)
        else:axis/=sine
        x,y,z=axis
        skew=np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
        rotation=np.eye(3)+sine*skew+(1-cosine)*(skew@skew)
        u,_,vt=np.linalg.svd(rotation@self.camera_position["rotation"])
        self.camera_position["rotation"]=u@np.diag([1.,1.,np.linalg.det(u@vt)])@vt


    def update_geometry(self,geometry,wall_chunks=None):
        self._reference_mode = False
        self.model_label = "3D • Impeller"
        lines,spanwise=self._profile_lines(geometry)
        chunks={name:[getattr(geometry,name)] for name in ("hub","shroud")} if wall_chunks is None else wall_chunks
        lines.update(self._wall_lines(chunks))
        self.surfaces=self._wall_surfaces(geometry,chunks)
        self._analysis_surfaces(chunks.get('analysis_shroud',
            [geometry.analysis_shroud.wall] if geometry.analysis_shroud is not None else []))
        self._tip_surfaces([geometry])
        self._line_blade_counts={}
        self.base_lines=lines;self.spanwise_lines=spanwise;self._rebuild_lines()

    @staticmethod
    def _profile_lines(geometry):
        lines,spanwise=Preview3D._section_lines(geometry.sections)
        if geometry.splitter_sections:
            extra,connections=Preview3D._section_lines(geometry.splitter_sections)
            for name,(xyz,color) in extra.items():
                label="Spanwise Splitter "+name[9:] if name.startswith("Spanwise ") else "Splitter "+name
                lines[label]=(xyz,color)
            spanwise.extend(connections)
        return lines,spanwise

    def update_surface_reference(self,lines,label):
        """Blade patches only; no source walls, caps or solid validity implied."""
        self._reference_mode=True
        self.surfaces={};self.base_lines=dict(lines);self.spanwise_lines=[];self._line_blade_counts={}
        for key in ('hub','shroud','tip_wall','analysis_shroud'):self.visibility_controls[key].hide()
        self.model_label=label;self._rebuild_lines()

    @staticmethod
    def _section_lines(sections):
        spanwise=build_spanwise_wireframe(sections)
        lines={}
        for section in sections:
            label="Hub" if section.span==0 else "Tip" if section.span==1 else f"Span {section.span:.6g}"
            for name,color in (("le","#e5c76b"),("ps","#56d9e0"),("te","#eead72"),("ss","#f6948c"),("camber","#aab4c5")):
                lines[f"{label} {name}"]=(getattr(section,"master_"+name if name!="camber" else name).xyz,color)
        for line in spanwise:
            lines[f"Spanwise {line.segment} {line.segment_index}"]=(line.xyz,"#496b8e")
        return lines,spanwise

    def update_diffuser(self, geometry,wall_chunks=None):
        """Display the diffuser's meridional sections and spanwise connections."""
        self.update_geometry(geometry,wall_chunks)
        self.model_label = "3D • Diffuser"

    def update_rows(self,rows,walls,analysis_chunks=None):
        """Compose independent rows; each row retains its own annulus count."""
        self._reference_mode=False
        lines={};counts={};spanwise=[]
        for identifier,name,geometry,count in rows:
            row_lines,row_spanwise=self._profile_lines(geometry)
            for key,value in row_lines.items():
                label=(f"Spanwise {name} [{identifier}] {key[9:]}" if key.startswith("Spanwise ")
                       else f"{name} [{identifier}] {key}")
                lines[label]=value;counts[label]=count
            spanwise.extend(row_spanwise)
        reference=walls.source_geometry or walls
        chunks={name:[getattr(reference,name)] for name in ("hub","shroud")}
        chunks['shroud'].extend(g.shroud for _,_,g,_ in rows if g.trim_report is not None and hasattr(g.shroud,'source_m'))
        lines.update(self._wall_lines(chunks));counts.update(Hub=1,Shroud=1)
        self.surfaces=self._wall_surfaces(walls,chunks)
        self._analysis_surfaces(analysis_chunks if analysis_chunks is not None else
            [g.analysis_shroud.wall for _,_,g,_ in rows if g.analysis_shroud is not None])
        self._tip_surfaces([geometry for _,_,geometry,_ in rows])
        self.base_lines=lines;self.spanwise_lines=spanwise;self._line_blade_counts=counts
        self.model_label=f"3D • All blade rows ({len(rows)})"
        self._rebuild_lines()

    @staticmethod
    def _wall_lines(chunks):
        result={}
        for name,color in (("hub","#56d9e0"),("shroud","#eead72")):
            points=[np.column_stack((c.r,np.zeros_like(c.r),c.z)) for c in chunks[name]]
            result[name.title()]=(np.concatenate(points) if points else np.empty((0,3)),color)
        return result

    def _analysis_surfaces(self,chunks):
        self.visibility_controls['analysis_shroud'].setVisible(bool(chunks))
        if chunks:self.surfaces['analysis_shroud']=(np.concatenate([revolve_wall(w) for w in chunks]),'#d59cfa')

    def _tip_surfaces(self,geometries):
        from types import SimpleNamespace
        profiles=[g.sections[-1].camber for g in geometries if g.tip is not None]
        box=self.visibility_controls['tip_wall'];box.setVisible(bool(profiles))
        self.visibility_controls['shroud'].setText('Casing' if profiles else 'Shroud')
        if profiles:
            self.surfaces['tip_wall']=(np.concatenate([revolve_wall(SimpleNamespace(z=p.z,r=p.r)) for p in profiles]),'#8deb87')

    @staticmethod
    def _wall_surfaces(geometry,chunks=None):
        chunks={name:[getattr(geometry,name)] for name in ("hub","shroud")} if chunks is None else chunks
        return {name:(np.concatenate([revolve_wall(wall) for wall in walls]),color)
                for name,color in (("hub","#56d9e0"),("shroud","#eead72"))
                if (walls:=chunks[name])}

    def visible_surfaces(self):
        for category,data in self.surfaces.items():
            if self.visibility_controls[category].isChecked():yield data
        if getattr(self,"_cad_visible",False):
            groups=self._cad_data["triangles"]
            full=self.cad_controls["full"].isChecked()
            if full and self._cad_data.get("triangles_full"):groups=self._cad_data["triangles_full"]
            elif not full and self._cad_data["scope"]!="periodic_sector" and self._cad_data.get("triangles_single"):groups=self._cad_data["triangles_single"]
            repeat=full and not self._cad_data.get("triangles_full") and self._cad_data["scope"] in ("blade_only","blade_hub")
            for name,triangles in groups.items():
                kind="root" if "FILLET" in name else "blade" if name.startswith("BLADE_") else "disk"
                if not self.cad_controls[kind].isChecked() or len(triangles)==0:continue
                xyz=np.asarray(triangles,dtype=float)[:,[0,1,2,2],:]
                color={"root":"#e8bd42","blade":"#75c6fa","disk":"#a8abb2"}[kind]
                if repeat and kind!="disk":
                    for i in range(self._cad_data["blade_count"]):
                        points=xyz.copy();points[:,:,0],points[:,:,1]=rotate_xy(xyz[:,:,0],xyz[:,:,1],2*np.pi*i/self._cad_data["blade_count"])
                        yield points,color
                else:yield xyz,color

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
                count=self._line_blade_counts.get(name,self.blade_count)
                for index in range(count):
                    x,y=rotate_xy(points[:,0],points[:,1],2*np.pi*index/count)
                    self.lines[f"{name} • blade {index+1}"]=(np.column_stack((x,y,points[:,2])),color)
        self.update()

    def visible_lines(self):
        # Draw span grid first so the bright profile outlines remain visible.
        ordered=sorted(self.lines.items(),key=lambda item:not item[0].startswith("Spanwise "))
        for name,data in ordered:
            name=name.split(" • blade ")[0]
            if name in ("Hub","Shroud"):continue  # walls are surfaces, not polylines
            category="hub" if name=="Hub" else "shroud" if name=="Shroud" else "spanwise" if name.startswith("Spanwise ") else "profiles"
            if self.visibility_controls[category].isChecked():yield data
        if getattr(self,"_cad_visible",False) and self.cad_controls["edges"].isChecked():
            for row in self._cad_data.get("edges",[]):yield np.asarray(row),"#edf0f4"


    def set_cad_mesh(self,data):
        self._cad_mesh_generation+=1
        self._cad_data=data;self._cad_snapshot_hash=data["snapshot_hash"];self._cad_visible=True
        if not hasattr(self,"cad_controls"):
            self._cad_source_visibility={key:self.visibility_controls[key].isChecked() for key in ("profiles","spanwise")}
            self._cad_overlay_visibility={key:(value if data['scope']=='disk_only' else False) for key,value in self._cad_source_visibility.items()}
            row=QHBoxLayout();self.layout().insertLayout(1,row);self._plot_top+=28;self.cad_controls={}
            for key,label,checked in (("blade","CAD Blade",True),("disk","Hub Disk",True),("root","Root Fillet",True),("full","CAD Full",False),("edges","Surface Edges",False)):
                box=QCheckBox(label);box.setChecked(checked);box.toggled.connect(self.update);row.addWidget(box);self.cad_controls[key]=box
            row.addStretch()
            if data['scope']!='disk_only':
                self.visibility_controls["profiles"].setChecked(False);self.visibility_controls["spanwise"].setChecked(False)
        roles=data["triangles"]
        has_blade=any(name.startswith('BLADE_') and len(rows)>0 for name,rows in roles.items())
        has_root=any("FILLET" in name and len(rows)>0 for name,rows in roles.items())
        has_disk=any(not name.startswith("BLADE_") and "FILLET" not in name and len(rows)>0 for name,rows in roles.items())
        self.cad_controls["root"].setEnabled(has_root);self.cad_controls["root"].setText("Root Fillet" if has_root else "No Root Fillet")
        self.cad_controls['blade'].setEnabled(has_blade);self.cad_controls['blade'].setText('CAD Blade' if has_blade else 'No CAD Blade')
        self.cad_controls["disk"].setEnabled(has_disk);self.cad_controls["disk"].setText("Hub Disk" if has_disk else "No Hub Disk")
        self.cad_controls["full"].setChecked(data["scope"]=="full_impeller")
        self.update()

    def sync_cad_snapshot(self,digest,enabled=True):
        visible=enabled and digest==self._cad_snapshot_hash
        if visible!=self._cad_visible:
            if not visible:
                self._cad_overlay_visibility={key:self.visibility_controls[key].isChecked() for key in self._cad_source_visibility}
            values=self._cad_overlay_visibility if visible else self._cad_source_visibility
            for key,value in values.items():self.visibility_controls[key].setChecked(value)
        self._cad_visible=visible
        self.update()

    def fit_view(self):
        if not self.lines:return
        xyz=np.concatenate([points for points,color in self.lines.values()]
                           +[faces.reshape(-1,3) for faces,color in self.surfaces.values()]
                           +([faces.reshape(-1,3) for faces,color in self.visible_surfaces()] if getattr(self,"_cad_visible",False) else []))
        self.camera_position["center"]=(xyz.min(axis=0)+xyz.max(axis=0))/2
        right,up,_=self._view_basis()
        relative=xyz-self.camera_position["center"]
        projected_center=np.array([(np.min(relative@axis)+np.max(relative@axis))/2 for axis in (right,up)])
        self.camera_position["center"]+=right*projected_center[0]+up*projected_center[1]
        projected=np.array([np.ptp(xyz@right),np.ptp(xyz@up)])
        factor=min(max(self.width(),1)/max(projected[0],1e-6),max(self.height()-self._plot_top-25,1)/max(projected[1],1e-6))/1.2
        self.camera_position["scale"]=max(min(self.width(),self.height())/(2*factor),1e-6)
        self.camera_position["pan"]=np.array([0.,12.5/factor]);self.update()

    def _poll_surface_image(self):
        if self._surface_render.poll():self.update()
        if not self._surface_render.busy:self._surface_poll.stop()

    def _cancel_surface_image(self):
        self._surface_render.cancel()
        if self._surface_render.busy:self._surface_poll.start()

    def _surface_scene_key(self):
        return (self._cad_mesh_generation,id(self._cad_data),tuple((name,id(data[0]),data[1]) for name,data in self.surfaces.items()),
            tuple(box.isChecked() for box in self.visibility_controls.values()),
            tuple(box.isChecked() for box in self.cad_controls.values()))

    def _surface_frame_key(self,scene):
        c=self.camera_position
        return (scene,self.width(),self.height(),self._plot_top,self.devicePixelRatioF(),
            c['azimuth'],c['elevation'],c['scale'],*c['rotation'].ravel(),*c['center'],*c['pan'])

    def _paint_surfaces(self,painter,camera,right,up,factor):
        if not getattr(self,'_cad_visible',False):
            self._cancel_surface_image();return self._paint_surfaces_sync(painter,camera,right,up,factor)
        scene=self._surface_scene_key()
        if self._surface_cache is None or self._surface_cache[0]!=scene:
            visible=list(self.visible_surfaces())
            if sum(len(rows) for rows,_ in visible)<=self._surface_async_threshold:
                self._surface_cache=None;self._cancel_surface_image()
                return self._paint_surfaces_sync(painter,camera,right,up,factor)
            faces=np.concatenate([rows for rows,_ in visible]);faces.setflags(write=False)
            colors=tuple(color for rows,color in visible for _ in rows)
            self._surface_cache=(scene,faces,colors)
        _,faces,colors=self._surface_cache;key=self._surface_frame_key(scene);renderer=self._surface_render
        if renderer.reuse(key):
            painter.drawImage(QPointF(0,0),renderer.image);return
        if renderer.desired_key!=key:
            arrays=[np.array(a,copy=True) for a in (camera['center'],camera['pan'],right,up)]
            for array in arrays:array.setflags(write=False)
            frame=SurfaceFrame(faces,colors,*arrays,factor,self.width(),self.height(),self._plot_top,self.devicePixelRatioF())
            renderer.request(key,frame);self._surface_poll.start()
        # Temporary display only; exact polygons replace this after rendering.
        painter.setPen(QPen(QColor('#74859b'),.8))
        for row in faces[::max(1,int(np.ceil(len(faces)/1000)))]:
            relative=row-camera['center'];x=(relative@right+camera['pan'][0])*factor+self.width()/2
            y=-(relative@up+camera['pan'][1])*factor+(self.height()+self._plot_top)/2
            painter.drawPolyline(QPolygonF([QPointF(float(a),float(b)) for a,b in zip(x,y)]))
        painter.setPen(QColor('#d1dae7'))
        painter.drawText(12,self._plot_top+18,'CAD rendering failed' if renderer.error else 'Rendering CAD surfaces...')

    def hideEvent(self,event):
        self._cancel_surface_image();super().hideEvent(event)

    def closeEvent(self,event):
        self._cancel_surface_image();super().closeEvent(event)

    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor("#101c2b"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        camera=self.camera_position;right,up,_=self._view_basis()
        factor=min(self.width(),self.height())/(2*camera["scale"])
        painter.save();painter.setClipRect(0,self._plot_top,self.width(),max(0,self.height()-self._plot_top-25))
        self._paint_surfaces(painter,camera,right,up,factor)
        for points,color in self.visible_lines():
            relative=points-camera["center"]
            x=(relative@right+camera["pan"][0])*factor+self.width()/2
            y=-(relative@up+camera["pan"][1])*factor+(self.height()+self._plot_top)/2
            painter.setPen(QPen(QColor(color),1.4))
            painter.drawPolyline(QPolygonF([QPointF(float(xx),float(yy)) for xx,yy in zip(x,y)]))
        painter.restore();painter.setPen(QColor("#d1dae7"))
        painter.drawText(12,self._plot_top-8,self.model_label)
        caption="XYZ [mm] • Z axis • CAD reference (sampled)" if self._reference_mode else "XYZ [mm] • Z axis • revolved walls / blade wireframe"
        painter.drawText(12,self.height()-14,caption)
        painter.end()

    def _paint_surfaces_sync(self,painter,camera,right,up,factor):
        visible=list(self.visible_surfaces())
        if not visible:return
        faces=np.concatenate([data[0] for data in visible])
        colors=[color for data,color in visible for _ in data]
        relative=faces-camera["center"]
        x=(relative@right+camera["pan"][0])*factor+self.width()/2
        y=-(relative@up+camera["pan"][1])*factor+(self.height()+self._plot_top)/2
        direction=np.cross(right,up)
        depth=np.mean(relative@direction,axis=1)
        normals=np.cross(faces[:,2]-faces[:,0],faces[:,3]-faces[:,1])
        lengths=np.linalg.norm(normals,axis=1)
        lighting=np.divide(np.abs(normals@direction),lengths,out=np.zeros_like(lengths),where=lengths>1e-12)
        painter.setPen(Qt.PenStyle.NoPen)
        for i in np.argsort(depth):
            color=QColor(colors[i]); shade=.55+.45*lighting[i]
            color.setRgbF(color.redF()*shade,color.greenF()*shade,color.blueF()*shade,.28)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([QPointF(float(xx),float(yy)) for xx,yy in zip(x[i],y[i])]))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def mousePressEvent(self,event):
        if getattr(self,"_cad_visible",False) and self.cad_controls["root"].isChecked():
            right,up,_=self._view_basis();camera=self.camera_position;factor=min(self.width(),self.height())/(2*camera["scale"])
            for faces,color in self.visible_surfaces():
                if color!="#e8bd42":continue
                for triangle in faces:
                    relative=np.asarray(triangle)-camera["center"]
                    x=(relative@right+camera["pan"][0])*factor+self.width()/2
                    y=-(relative@up+camera["pan"][1])*factor+(self.height()+self._plot_top)/2
                    polygon=QPolygonF([QPointF(float(a),float(b)) for a,b in zip(x,y)])
                    if polygon.containsPoint(event.position(),Qt.FillRule.OddEvenFill):
                        QToolTip.showText(event.globalPosition().toPoint(),f"True CAD Hub Fillet R = {self._cad_data['fillet_radius_mm']:g} mm",self);break
        self._last=(event.position() if self._plot_top<=event.position().y()<self.height()-25 else None)
        event.accept()

    def mouseMoveEvent(self,event):
        if self._last is None:return
        previous=self._last;delta=event.position()-previous;self._last=event.position()
        camera=self.camera_position
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._rotate_trackball(previous,event.position())
        elif event.buttons() & Qt.MouseButton.RightButton:
            factor=2*camera["scale"]/max(1,min(self.width(),self.height()))
            camera["pan"]+=np.array([delta.x(),-delta.y()])*factor
        self.update();event.accept()

    def mouseReleaseEvent(self,event):self._last=None;event.accept()

    def wheelEvent(self,event):
        self.camera_position["scale"]=float(np.clip(self.camera_position["scale"]*np.exp(-event.angleDelta().y()/1200),1e-6,1e12))
        self.update();event.accept()
