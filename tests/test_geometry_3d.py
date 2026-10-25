from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.span import interpolate_span_position
from blade_designer.models.parameters import BladeParameters,BladeSection,BladeAngleParameters,DistributionPoint
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters


def test_cylindrical_and_cartesian_section_counts_and_joins():
 p=BladeParameters();p.sections.insert(1,BladeSection(.5))
 g=generate_impeller(p)
 assert [s.span for s in g.sections]==[0,.5,1]
 for section in g.sections:
  assert len(section.camber.r)==2001
  assert [len(getattr(section,name).r) for name in ('le','ps','te','ss')]==[21,101,21,101]
  for curve in (section.camber,section.le,section.ps,section.te,section.ss):
   np.testing.assert_allclose(np.hypot(curve.x,curve.y),curve.r,atol=1e-12)
   assert np.isfinite(curve.xyz).all()
  for a,b,ia,ib in ((section.le,section.ps,-1,0),(section.ps,section.te,-1,0),(section.te,section.ss,-1,-1),(section.ss,section.le,0,0)):
   np.testing.assert_allclose(a.xyz[ia],b.xyz[ib],atol=1e-13)
  assert section.camber.m_norm[0]==0 and section.camber.m_norm[-1]==1
 g2=generate_impeller(deepcopy(p));np.testing.assert_allclose(g.sections[0].camber.xyz,g2.sections[0].camber.xyz)
 wall=interpolate_span_position(g.hub,g.shroud,.5,np.array([0,.5,1]))
 np.testing.assert_allclose(wall,(interpolate_span_position(g.hub,g.shroud,0,np.array([0,.5,1]))+interpolate_span_position(g.hub,g.shroud,1,np.array([0,.5,1])))/2)


def test_constant_radius_angle_definition():
 p=BladeParameters()
 p.hub=MeridionalCurveParameters(0,50,0,[LineSegmentParameters(100)])
 p.shroud=MeridionalCurveParameters(0,70,0,[LineSegmentParameters(100)])
 for s in p.sections:s.blade_angle=BladeAngleParameters([DistributionPoint(0,30),DistributionPoint(1,30)])
 g=generate_impeller(p)
 for s,r in zip(g.sections,[50,70]):
  np.testing.assert_allclose(s.camber.theta_rad,(s.m-s.m[0])*np.tan(np.pi/6)/r,atol=1e-13)
  np.testing.assert_allclose(s.camber.r,r)
  np.testing.assert_allclose(s.camber.z,s.m)


def test_independent_tip_and_output_resolution():
 p=BladeParameters();before=generate_impeller(p)
 p.sections[1].blade_angle.points[1].value=30
 p.sections[1].thickness.points[1].value=6
 p.output_points.ps_points=51
 after=generate_impeller(p)
 np.testing.assert_allclose(before.sections[0].camber.xyz,after.sections[0].camber.xyz)
 np.testing.assert_allclose(before.sections[0].master_ps.xyz,after.sections[0].master_ps.xyz)
 assert not np.allclose(before.sections[1].camber.xyz,after.sections[1].camber.xyz)
 assert len(after.sections[0].ps.r)==51


@pytest.mark.parametrize('kind',['span','distribution','edge','extent','intersection'])
def test_invalid_3d(kind):
 p=BladeParameters()
 if kind=='span':p.sections[1].span=.5
 if kind=='distribution':p.sections[1].thickness.points[1].value=-1
 if kind=='edge':p.sections[1].edge_parameters.le_ellipse_ratio=float('nan')
 if kind=='extent':p.sections[0].thickness.points[0].value=500
 if kind=='intersection':p.shroud=deepcopy(p.hub)
 with pytest.raises(ValueError):generate_impeller(p)


def test_hub_tip_independent_edges_on_axial_wall():
 from blade_designer.models.parameters import EdgeType,ThicknessParameters
 p=BladeParameters()
 p.hub=MeridionalCurveParameters(0,50,0,[LineSegmentParameters(100)])
 p.shroud=MeridionalCurveParameters(0,70,0,[LineSegmentParameters(100)])
 for section in p.sections:
  section.blade_angle.points=[DistributionPoint(0,0),DistributionPoint(1,0)]
  section.thickness.points=[DistributionPoint(0,4),DistributionPoint(1,4)]
 p.sections[1].edge_parameters.le_type=EdgeType.ELLIPTICAL
 p.sections[1].edge_parameters.le_ellipse_ratio=2
 hub,tip=generate_impeller(p).sections
 # Rounded noses now own the specified LE/TE; the camber reference is kept.
 assert hub.master_le.z.min()==pytest.approx(100*p.impeller_edges.leading_edge.hub_m_flow_norm)
 assert tip.master_le.z.min()==pytest.approx(100*p.impeller_edges.leading_edge.shroud_m_flow_norm)
 assert hub.master_te.z.max()==pytest.approx(100*p.impeller_edges.trailing_edge.hub_m_flow_norm)
 assert tip.master_te.z.max()==pytest.approx(100*p.impeller_edges.trailing_edge.shroud_m_flow_norm)


def test_axial_tip_cutoff_rejects_unreachable_hub_radius():
 from blade_designer.models.parameters import EdgeType
 p=BladeParameters()
 p.hub=MeridionalCurveParameters(0,50,0,[LineSegmentParameters(100)])
 p.shroud=MeridionalCurveParameters(0,70,0,[LineSegmentParameters(100)])
 p.sections[1].edge_parameters.te_type=EdgeType.CUTOFF
 with pytest.raises(ValueError,match="does not reach the Hub TE cylinder"):
  generate_impeller(p)


def test_zero_interior_thickness_rejects_collapsed_profile():
 p=BladeParameters()
 for point in p.sections[1].thickness.points:point.value=0
 with pytest.raises(ValueError,match='self intersection|zero interior'):
  generate_impeller(p)


def test_intermediate_le_te_stations_interpolate_walls():
 p=BladeParameters();p.sections.insert(1,BladeSection(.25))
 hub,middle,tip=generate_impeller(p).sections
 for index in (0,-1):
  expected=.75*np.array([hub.camber.z[index],hub.camber.r[index]])+.25*np.array([tip.camber.z[index],tip.camber.r[index]])
  np.testing.assert_allclose([middle.camber.z[index],middle.camber.r[index]],expected,atol=2e-6)
