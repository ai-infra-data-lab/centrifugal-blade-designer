import json
from copy import deepcopy
from dataclasses import asdict
import pytest
from blade_designer.models.parameters import BladeParameters,BladeSection,EdgeType
from blade_designer.models.meridional import ArcSegmentParameters
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.project_migration import migrate_v02_to_v03


def old_v02():
 p=BladeParameters();p.blade_angle.points[1].value=45;p.edges.le_type=EdgeType.ELLIPTICAL;p.edges.le_ellipse_ratio=1.5
 d=asdict(p)
 return {'schema_version':'0.2',**{k:d[k] for k in ('geometry','blade_angle','thickness','edges','output_points','export','surface_mapping')}}


def test_v02_migration_preserves_all_and_clones_tip(tmp_path):
 old=old_v02();before=deepcopy(old)
 migrated=migrate_v02_to_v03(old)
 assert old==before and migrated['schema_version']=='0.3'
 path=tmp_path/'old.json';path.write_text(json.dumps(old));original=path.read_text()
 p=load_project(path)
 assert p.sections[0].blade_angle==p.sections[1].blade_angle
 assert p.sections[0].edge_parameters==p.sections[1].edge_parameters
 assert p.blade_angle.points[1].value==45
 assert p.edges.le_type==EdgeType.ELLIPTICAL
 p.sections[1].blade_angle.points[1].value=20
 assert p.blade_angle.points[1].value==45
 assert path.read_text()==original
 save_project(tmp_path/'new.json',p);assert load_project(tmp_path/'new.json')==p


def test_full_v03_precision_and_primitive_roundtrip(tmp_path):
 p=BladeParameters();p.sections.insert(1,BladeSection(.2512345678901234))
 p.sections[1].thickness.points[1].value=4.123456789012345
 p.hub.start_z=.123456789012345;p.shroud.start_z=.123456789012345
 p.hub.segments[1].radius=30.123456789012345
 p.turbogrid.geometry_unit='CM';p.turbogrid.rotation_axis='X'
 p.turbogrid.profile_curve_filename='blade.curve'
 p.blade_le_fraction=.1512345678901234;p.hub.export_points=321
 path=tmp_path/'new.json';save_project(path,p)
 assert json.loads(path.read_text())['schema_version']=='0.3'
 assert load_project(path)==p
 assert isinstance(load_project(path).hub.segments[1],ArcSegmentParameters)


@pytest.mark.parametrize('kind',['curve','section','nan','fraction','axis'])
def test_invalid_v03_rejected(tmp_path,kind):
 p=BladeParameters();path=tmp_path/'bad.json';save_project(path,p);d=json.loads(path.read_text())
 if kind=='curve':d['hub']['segments'][1]['radius']=-1
 if kind=='section':d['sections'][1]['span']=0
 if kind=='nan':d['shroud']['start_z']=float('nan')
 if kind=='fraction':d['blade_le_fraction']=.9
 if kind=='axis':d['turbogrid']['rotation_axis']='W'
 path.write_text(json.dumps(d))
 with pytest.raises(ValueError):load_project(path)
