"""Actual owned wall curves for independent connected elements."""
import pyqtgraph as pg
from ..models.blade_rows import row_parameters
from ..geometry.element_walls import generate_wall_element
from ..geometry.row_domain import preview_wall_chunks
from ..geometry.blade_edge import edge_endpoints


class ElementMeridionalView(pg.PlotWidget):
    def __init__(self):
        super().__init__();self.setBackground('#101f2c');self.addLegend()
        self.setLabel('bottom','Z [mm]');self.setLabel('left','R [mm]')
        self.setAspectLocked(True);self.showGrid(x=True,y=True,alpha=.2)
        self.wall_lines=[];self.edge_lines=[]

    def update_project(self,project,identifier=None):
        self.clear();self.plotItem.legend.clear();self.wall_lines=[];self.edge_lines=[]
        rows=[row for row in project.blade_rows or [] if identifier is None or row.identifier==identifier]
        for row in rows:
            params=row_parameters(project,row);geometry=generate_wall_element(params)
            chunks=preview_wall_chunks(params,geometry,row.identifier)
            for name,color in (('hub','#56d9e0'),('shroud','#eead72')):
                for index,chunk in enumerate(chunks[name]):
                    item=self.plot(chunk.z,chunk.r,pen=pg.mkPen(color,width=2),
                        name=f'{row.name} {name.title()}' if index==0 else None)
                    self.wall_lines.append(item)
            if identifier is not None and row.kind!='meridional':
                edges=getattr(params,row.kind+'_edges')
                for name in ('leading_edge','trailing_edge'):
                    zr=edge_endpoints(getattr(edges,name),geometry.hub,geometry.shroud)
                    self.edge_lines.append(self.plot(zr[:,0],zr[:,1],pen=pg.mkPen('#b7a1ff'),symbol='o',
                        name='LE' if name=='leading_edge' else 'TE'))
        self.setTitle('Connected Meridional Elements' if identifier is None else next(row.name for row in rows))
