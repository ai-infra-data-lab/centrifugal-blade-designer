"""Station-aware R-Z context view with persistent graphics items."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel
from .plot_widgets import configure_plot
from ..models.flow_path import StationType
from ..geometry.flow_area import crossflow_pair
from ..geometry.flow_path import validate_component_stations,component_regions,sample_mean_line

class ContextMeridional(QWidget):
    stationSelected=Signal(float)
    endpointMoved=Signal(str,str,str,float)
    edgeDragStarted=Signal()
    edgeDragFinished=Signal()

    def __init__(self):
        super().__init__()
        layout=QVBoxLayout(self)
        self.legend=QLabel();self.legend.setWordWrap(True);layout.addWidget(self.legend)
        self.plot=pg.PlotWidget(background="#101c2b")
        configure_plot(self.plot,"Z [mm]","R [mm]")
        self.plot.setAspectLocked(True);self.plot.addLegend()
        self.curves=[self.plot.plot(pen=pg.mkPen(c,width=2),name=n)
                     for c,n in (("#56d9e0","Hub"),("#eead72","Shroud"))]
        self.tip_profiles={}
        self.trim_profiles={}
        self._tip_visible=False
        self.boundaries=[self.plot.plot(pen=pg.mkPen("#909cac",style=__import__("PySide6.QtCore",fromlist=["Qt"]).Qt.PenStyle.DashLine))
                         for _ in StationType]
        self.region_labels=[]
        for item in self.region_labels:self.plot.addItem(item,ignoreBounds=True)
        self.cursor=self.plot.plot(pen=pg.mkPen("#f8e067",width=3))
        from .blade_edge_handles import BladeEdgeHandles
        self.edge_handles=[BladeEdgeHandles(self,key,side,color) for key,side,color in (
            ('impeller_edges','leading_edge','#89ef85'),('impeller_edges','trailing_edge','#f6e16a'),
            ('diffuser_edges','leading_edge','#f896c6'),('diffuser_edges','trailing_edge','#b4a3ff'))]
        self.station_points=None
        self.plot.scene().sigMouseClicked.connect(self._clicked)
        row=QHBoxLayout()
        row.addWidget(self.plot,3)
        self.region_legend=QLabel()
        self.region_legend.setWordWrap(True);self.region_legend.setMinimumWidth(220)
        row.addWidget(self.region_legend,1)
        layout.addLayout(row);self.plot.disableAutoRange()
        self.row_scale=QLabel();self.row_scale.setWordWrap(True);layout.addWidget(self.row_scale)
        self.coordinate_map=None

    def update_geometry(self,geometry,parameters=None,mean_points=4001):
        for item,wall in zip(self.curves,(geometry.hub,geometry.shroud)):item.setData(wall.z,wall.r)
        self.update_tip_profiles([('Impeller',geometry)] if getattr(geometry,'tip',None) is not None else [])
        if parameters is None:return
        from ..geometry.meridional_segments import sample_meridional
        values=validate_component_stations(parameters)
        u,mean,tangents,_=sample_mean_line(geometry.hub,geometry.shroud,values,mean_points)
        h=sample_meridional(geometry.hub,u*geometry.hub.length)
        s=sample_meridional(geometry.shroud,u*geometry.shroud.length)
        self.station_points=mean;self.station_values=values
        self.legend.setText("  |  ".join(f"{k.value}: {v:.4g}" for k,v in zip(StationType,values)))
        self.cursor.setData([],[])
        for item,p,t,a,b in zip(self.boundaries,mean,tangents,h,s):
            if parameters.align_blade_stations_to_crossflow:
                try:a,b=crossflow_pair(geometry.hub,geometry.shroud,p,t,a,b)
                except ValueError:pass  # Finite-wall gaps are reported by the area engine.
            item.setData([a[0],b[0]],[a[1],b[1]])
        regions=component_regions(parameters)
        _,centers,_,_=sample_mean_line(geometry.hub,geometry.shroud,np.array([(r.start+r.end)/2 for r in regions]),mean_points)
        # Full region names remain readable in the text legend; short plot labels aid orientation.
        self.legend.setToolTip(" → ".join(r.name for r in regions))
        self.region_legend.setText("<br>".join(f"<b>{r.name}</b>: {r.start:.4g} → {r.end:.4g}" for r in regions))
        for item,region,p in zip(self.region_labels,regions,centers):
            item.setText(region.name.replace(" Diffuser","\nDiffuser").replace(" / Gap",""))
            item.setPos(*p)

    def update_blade_edges(self,geometry,parameters):
        from ..geometry.blade_edge import edge_endpoints
        groups=([(row.identifier,row.name,getattr(row.parameters,row.kind+"_edges")) for row in parameters.blade_rows]
                if parameters.blade_rows is not None else [(key,name,getattr(parameters,key))
                for key,name in (("impeller_edges","Impeller"),("diffuser_edges","Diffuser"))])
        from ..geometry.row_coordinates import build_row_coordinates
        try:
            coordinates=build_row_coordinates([parameters.hub,parameters.shroud],[key for key,name,edges in groups])
            error=''
        except (ValueError,ArithmeticError) as exc:coordinates=None;error=str(exc)
        self.set_row_coordinates(coordinates,{key:name for key,name,edges in groups},error)
        self.update_edge_groups(geometry,groups)
        stations=list(StationType)
        for key,prefix in (("impeller_edges","IMP"),("diffuser_edges","DIF")):
            for side,suffix in (("leading_edge","LE"),("trailing_edge","TE")):
                points=edge_endpoints(getattr(getattr(parameters,key),side),geometry.hub,geometry.shroud)
                self.boundaries[stations.index(StationType(prefix+"_"+suffix))].setData(points[:,0],points[:,1])
        self.legend.setToolTip("Scalar Component Stations are used for Flow Area. Visible IMP/DIF boundaries follow the independent blade edges.")

    def set_row_coordinates(self,coordinates,names,error=''):
        self.coordinate_map=coordinates
        if coordinates is None:
            self.row_scale.setText('翼列距離 s: 未設定 — '+error)
        else:
            self.row_scale.setText('子午面の翼列距離 s: '+'  |  '.join(
                f'{i}–{i+1} {names[key]}' for i,key in enumerate(coordinates.order)))

    def update_edge_groups(self,geometry,groups):
        from .blade_edge_handles import BladeEdgeHandles
        desired=[(key,side) for key,name,edges in groups for side in ("leading_edge","trailing_edge")]
        existing={(item.key,item.side):item for item in self.edge_handles}
        for key,item in list(existing.items()):
            if key not in desired:
                self.plot.plotItem.legend.removeItem(item.legend_item)
                for graphic in (item.legend_item,item.label,item):self.plot.removeItem(graphic)
                item.deleteLater();del existing[key]
        colors=("#89ef85","#f6e16a","#f896c6","#b4a3ff","#79baff","#f69f70")
        handles=[]
        for index,(key,name,edges) in enumerate(groups):
            for offset,side in enumerate(("leading_edge","trailing_edge")):
                item=existing.get((key,side))
                if item is None:item=BladeEdgeHandles(self,key,side,colors[(2*index+offset)%len(colors)])
                item.set_name(name);item.update_edge(edges,geometry.hub,geometry.shroud);handles.append(item)
                text='翼列距離 s: 未設定'
                if self.coordinate_map is not None:
                    try:
                        values=[self.coordinate_map.position(key,wall,getattr(getattr(edges,side),wall+'_m_flow_norm')) for wall in ('hub','shroud')]
                        text=f'{name} {"LE" if side=="leading_edge" else "TE"} • Hub s={values[0]:.8g} / Shroud s={values[1]:.8g}'
                    except (ValueError,KeyError):pass
                item.setToolTip(text)
        self.edge_handles=handles


    def show_crossflow(self,station):
        self.cursor.setData([station.hub_z,station.shroud_z],[station.hub_r,station.shroud_r])

    def update_tip_profiles(self,entries):
        trimmed={name:geometry for name,geometry in entries if geometry.trim_report is not None}
        for name,line in list(self.trim_profiles.items()):
            if name not in trimmed:
                self.plot.plotItem.legend.removeItem(line);self.plot.removeItem(line);del self.trim_profiles[name]
        for name,geometry in trimmed.items():
            if name not in self.trim_profiles:
                self.trim_profiles[name]=self.plot.plot(pen=pg.mkPen('#f4ba70',width=2),name=f'{name} Trim casing')
            self.trim_profiles[name].setData(geometry.shroud.z,geometry.shroud.r)
        enabled=bool(entries)
        if enabled!=self._tip_visible:
            label=self.plot.plotItem.legend.getLabel(self.curves[1])
            if label is not None:label.setText('Casing / Shroud' if enabled else 'Shroud')
            self._tip_visible=enabled
        names={name for name,_ in entries}
        for name,items in list(self.tip_profiles.items()):
            if name not in names:
                for item in items:
                    self.plot.plotItem.legend.removeItem(item)
                    self.plot.removeItem(item)
                del self.tip_profiles[name]
        for name,geometry in entries:
            if name not in self.tip_profiles:
                line=self.plot.plot(pen=pg.mkPen('#8deb87',width=2),name=f'{name} Tip (trim)' if geometry.trim_report else f'{name} Tip (clearance)')
                markers=self.plot.plot(pen=None,symbol='o',symbolBrush='#8deb87',symbolSize=7)
                self.tip_profiles[name]=(line,markers)
            profile=geometry.sections[-1].camber
            line,markers=self.tip_profiles[name]
            line.setData(profile.z,profile.r)
            markers.setData(profile.z[[0,-1]],profile.r[[0,-1]])

    def _clicked(self,event):
        if self.station_points is None or not self.plot.sceneBoundingRect().contains(event.scenePos()):return
        pos=self.plot.getViewBox().mapSceneToView(event.scenePos())
        index=int(np.argmin(np.linalg.norm(self.station_points-[pos.x(),pos.y()],axis=1)))
        self.stationSelected.emit(float(self.station_values[index]))

    def fit_view(self):
        self.plot.autoRange();self.plot.disableAutoRange()
