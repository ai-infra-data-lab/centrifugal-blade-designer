from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters,BladeSection
from blade_designer.fileio.turbogrid_export import export_turbogrid,closed_profile
from blade_designer.geometry.geometry_3d import generate_impeller


def read_profiles(path):
 profiles=[]
 for line in path.read_text().splitlines():
  if line.startswith('#'):profiles.append([])
  else:profiles[-1].append([float(v) for v in line.split()[:3]])
 return [np.array(p) for p in profiles]


def test_files_section_count_order_closure_and_precision(tmp_path):
 p=BladeParameters();p.sections.insert(1,BladeSection(.5));g=generate_impeller(p)
 files=export_turbogrid(tmp_path/'case',p)
 assert [f.name for f in files]==['hub.curve','shroud.curve','profile.curve','BladeGen.inf']
 assert all(f.exists() and f.stat().st_size>0 for f in files)
 profiles=read_profiles(files[2]);assert len(profiles)==3
 for actual,section in zip(profiles,g.sections):
  expected,markers=closed_profile(section)
  assert len(actual)==21+101+21+101-4+1
  assert np.isfinite(actual).all()
  np.testing.assert_allclose(actual,expected,rtol=6e-6,atol=6e-4)
  np.testing.assert_array_equal(actual[0],actual[-1])
  assert ' le' in files[2].read_text() and ' te' in files[2].read_text()
 hub=np.loadtxt(files[0]);shroud=np.loadtxt(files[1])
 assert len(hub)==501 and len(shroud)==501
 np.testing.assert_allclose(hub[0],[p.hub.start_r,0,p.hub.start_z])
 np.testing.assert_allclose(hub[-1],[g.hub.r[-1],0,g.hub.z[-1]])
 assert 'Axis of Rotation: Z' in files[3].read_text()
 assert 'Number of Blade Sets: 20' in files[3].read_text()
 assert 'Geometry Units: MM' in files[3].read_text()
 assert 'Number of Blades Per Set: 1' in files[3].read_text()
 assert 'Blade 0 LE: EllipseEnd' in files[3].read_text()
 assert 'Blade 0 TE: EllipseEnd' in files[3].read_text()


@pytest.mark.parametrize('axis,order',[('X',[2,0,1]),('Y',[1,2,0]),('Z',[0,1,2])])
def test_units_rotation_and_digits(tmp_path,axis,order):
 p=BladeParameters();p.turbogrid.rotation_axis=axis;p.turbogrid.geometry_unit='CM';p.export.significant_digits=15
 g=generate_impeller(p);files=export_turbogrid(tmp_path,p)
 profiles=read_profiles(files[2]);expected,_=closed_profile(g.sections[0])
 np.testing.assert_allclose(profiles[0],expected[:,order]*.1,rtol=6e-15,atol=1e-13)


def test_invalid_export_no_partial_files(tmp_path):
 p=BladeParameters();p.hub.segments[1].radius=-1
 with pytest.raises(ValueError):export_turbogrid(tmp_path/'bad',p)
 assert not (tmp_path/'bad').exists()
 p=BladeParameters();p.turbogrid.hub_curve_filename='../escape.curve'
 with pytest.raises(ValueError):export_turbogrid(tmp_path/'bad',p)
 assert not (tmp_path/'bad').exists()


def test_verified_cutoff_inf_setting(tmp_path):
 from blade_designer.models.parameters import EdgeType
 p=BladeParameters()
 for s in p.sections:s.edge_parameters.te_type=EdgeType.CUTOFF
 files=export_turbogrid(tmp_path,p)
 assert 'Blade 0 TE: CutOffEnd' in files[3].read_text()


def test_sharp_le_has_no_duplicate_interior_vertices(tmp_path):
 p=BladeParameters()
 for section in p.sections:section.thickness.points[0].value=0
 files=export_turbogrid(tmp_path,p)
 for profile in read_profiles(files[2]):
  assert np.all(np.linalg.norm(np.diff(profile,axis=0),axis=1)>0)
  np.testing.assert_array_equal(profile[0],profile[-1])


def test_station_update_preserves_explicit_contour_order_and_invalid_export(tmp_path):
 from blade_designer.models.flow_path import StationType
 import hashlib
 p=BladeParameters();p.export.significant_digits=15
 p.flow_path.set_position(StationType.IMP_LE,.2)
 p.flow_path.set_position(StationType.IMP_TE,.8)
 g=generate_impeller(p);files=export_turbogrid(tmp_path/'case',p)
 profiles=read_profiles(files[2])
 for actual,section in zip(profiles,g.sections):
  np.testing.assert_allclose(actual[0],section.le.xyz[0],atol=1e-12)
  np.testing.assert_allclose(actual[20],section.ps.xyz[0],atol=1e-12)
  np.testing.assert_allclose(actual[120],section.te.xyz[0],atol=1e-12)
  np.testing.assert_allclose(actual[140],section.ss.xyz[-1],atol=1e-12)
  np.testing.assert_allclose(actual[240],section.le.xyz[0],atol=1e-12)
 before={f:hashlib.sha256(f.read_bytes()).digest() for f in files}
 p.flow_path.stations[3].m_flow_norm=.7
 with pytest.raises(ValueError):export_turbogrid(tmp_path/'case',p)
 assert all(hashlib.sha256(f.read_bytes()).digest()==digest for f,digest in before.items())
 with pytest.raises(ValueError):export_turbogrid(tmp_path/'invalid',p)
 assert not (tmp_path/'invalid').exists()
