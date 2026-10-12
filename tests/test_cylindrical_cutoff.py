from copy import deepcopy
import numpy as np
import pytest
from blade_designer.models.parameters import (BladeParameters, BladeSection,
    DistributionPoint, EdgeType, RotationDirection, SurfaceMapping)
from blade_designer.models.meridional import MeridionalCurveParameters, LineSegmentParameters
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.fileio.project_io import save_project, load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid


def radial_parameters(beta=30):
    p=BladeParameters()
    p.hub=MeridionalCurveParameters(0,50,90,[LineSegmentParameters(100)])
    p.shroud=MeridionalCurveParameters(10,50,90,[LineSegmentParameters(100)])
    p.impeller_edges.trailing_edge.hub_m_flow_norm=.7
    p.impeller_edges.trailing_edge.shroud_m_flow_norm=.85
    p.sections.insert(1,BladeSection(.5))
    for s in p.sections:
        s.edge_parameters.te_type=EdgeType.CUTOFF
        s.blade_angle.points=[DistributionPoint(0,beta),DistributionPoint(1,beta)]
        s.thickness.points=[DistributionPoint(0,4),DistributionPoint(1,4)]
    return p


@pytest.mark.parametrize("beta",[-45,0,30,60])
@pytest.mark.parametrize("rotation",list(RotationDirection))
@pytest.mark.parametrize("mapping",list(SurfaceMapping))
def test_all_spans_trim_to_hub_cylinder_and_preserve_exact_joins(beta,rotation,mapping):
    p=radial_parameters(beta); p.rotation_direction=rotation; p.surface_mapping=mapping
    before=deepcopy(p); g=generate_impeller(p)
    assert p==before
    for s in g.sections:
        # Analytic straight radial wall: Hub TE R = 50 + .7 * 100 = 120.
        for te in (s.master_te,s.te):
            np.testing.assert_allclose(te.r,120,atol=1e-12,rtol=0)
            np.testing.assert_allclose(np.hypot(te.x,te.y),120,atol=1e-12,rtol=0)
            np.testing.assert_allclose(te.z,10*s.span,atol=1e-12)
        for name in ("ps","ss"):
            curve=getattr(s,"master_"+name)
            assert curve.r.max()<=120+1e-12
            assert curve.r[-1]==120
        np.testing.assert_array_equal(s.ps.xyz[-1],s.te.xyz[0])
        np.testing.assert_array_equal(s.ss.xyz[-1],s.te.xyz[-1])
        assert [len(getattr(s,n).r) for n in ("le","ps","te","ss")]==[21,101,21,101]


def test_short_side_extension_follows_terminal_angle_on_radial_wall():
    p=radial_parameters(30); p.surface_mapping=SurfaceMapping.POSITIVE_IS_PS
    s=generate_impeller(p).sections[0]
    # PS normal offset is -t*sin(beta)/2=-1 mm in m, so the virtual
    # camber must reach R=121 to put the actual PS endpoint at R=120.
    expected=s.camber.theta_rad[-1]+np.tan(np.pi/6)*np.log(121/120)+2*np.cos(np.pi/6)/120
    assert s.master_ps.theta_rad[-1]==pytest.approx(expected,abs=1e-12)


def test_cutoff_changes_with_hub_te_not_tip_te_or_diffuser_radius():
    p=radial_parameters(); before=generate_impeller(p)
    p.geometry.r_te=200
    p.impeller_edges.trailing_edge.shroud_m_flow_norm=.9
    after=generate_impeller(p)
    for s in after.sections: np.testing.assert_array_equal(s.master_te.r,before.sections[0].master_te.r)
    p.impeller_edges.trailing_edge.hub_m_flow_norm=.75
    for s in generate_impeller(p).sections: np.testing.assert_allclose(s.master_te.r,125)


def test_cutoff_roundtrip_and_turbogrid_coordinates(tmp_path):
    p=radial_parameters(); p.export.significant_digits=15
    path=tmp_path/"project.json"; save_project(path,p)
    assert load_project(path)==p
    g=generate_impeller(p); files=export_turbogrid(tmp_path/"export",p)
    assert "Blade 0 TE: CutOffEnd" in files[3].read_text()
    profiles=[]
    for line in files[2].read_text().splitlines():
        if line.startswith("#"): profiles.append([])
        else: profiles[-1].append([float(v) for v in line.split()[:3]])
    # Closed profile order: LE, PS, TE, reversed SS, with shared joins omitted.
    for profile,s in zip(profiles,g.sections):
        xyz=np.asarray(profile); start=len(s.le.r)+len(s.ps.r)-2
        te=xyz[start:start+len(s.te.r)]
        np.testing.assert_allclose(np.hypot(te[:,0],te[:,1]),120,atol=1e-11,rtol=0)


def test_cylinder_at_wall_end_does_not_place_physical_surface_outside_wall():
    p=radial_parameters()
    p.impeller_edges.trailing_edge.hub_m_flow_norm=1.
    p.impeller_edges.trailing_edge.shroud_m_flow_norm=1.
    p.impeller_edges.reference_te_fraction=1.
    for s in generate_impeller(p).sections:
        np.testing.assert_allclose(s.master_te.r,150,atol=1e-12)
        assert s.master_ps.meridional_distance.max()<=100+1e-12
        assert s.master_ss.meridional_distance.max()<=100+1e-12


def test_curved_wall_and_varying_distributions_still_end_on_one_cylinder():
    p=BladeParameters(); p.sections.insert(1,BladeSection(.4))
    from blade_designer.geometry.blade_edge import edge_endpoints
    for s in p.sections: s.edge_parameters.te_type=EdgeType.CUTOFF
    g=generate_impeller(p)
    radius=edge_endpoints(p.impeller_edges.trailing_edge,g.hub,g.shroud)[0,1]
    for s in g.sections:
        np.testing.assert_allclose(s.te.r,radius,rtol=0,atol=1e-12)
        np.testing.assert_array_equal(s.master_ps.xyz[-1],s.master_te.xyz[0])
        np.testing.assert_array_equal(s.master_ss.xyz[-1],s.master_te.xyz[-1])


def test_other_edge_types_and_diffuser_remain_unchanged():
    p=radial_parameters()
    for s in p.sections: s.edge_parameters.te_type=EdgeType.ELLIPTICAL
    from blade_designer.geometry.designer import BladeDesigner
    before=generate_impeller(p); diffuser=BladeDesigner().generate_diffuser(p)
    p.sections[-1].edge_parameters.te_type=EdgeType.CUTOFF
    after=generate_impeller(p); new_diffuser=BladeDesigner().generate_diffuser(p)
    for old,new in zip(before.sections[:-1],after.sections[:-1]):
        for name in ("camber","master_ps","master_ss","master_le","master_te"):
            np.testing.assert_array_equal(getattr(old,name).xyz,getattr(new,name).xyz)
    np.testing.assert_array_equal(diffuser.master_surfaces.te.xy,new_diffuser.master_surfaces.te.xy)


def test_cut_before_tip_le_rejects_export_without_partial_files(tmp_path):
    p=radial_parameters()
    p.impeller_edges.leading_edge.shroud_m_flow_norm=.8
    with pytest.raises(ValueError,match="m_TE must exceed m_LE"):
        export_turbogrid(tmp_path/"invalid",p)
    assert not (tmp_path/"invalid").exists()
