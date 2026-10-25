"""Single-circle contact motion, analytic tangency and geometry integration."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.interpolate import make_interp_spline
from blade_designer.geometry.tangent_arcs import SampledSide,fit_circular_cap,MAX_CONTACT_FRACTION
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.models.parameters import EdgeType,RotationDirection,SurfaceMapping,DistributionPoint,SplitterParameters
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.turbogrid_export import export_turbogrid,closed_profile
from test_cylindrical_cutoff import radial_parameters
from test_return_channel import return_channel_parameters


def dot(a,b):return np.dot(a,b)/np.linalg.norm(a)/np.linalg.norm(b)


def sides(k1,k2,length=10.):
    x=np.linspace(0,length,301)
    return SampledSide(np.column_stack((x,2+k1*x))),SampledSide(np.column_stack((x,-2-k2*x)))


@pytest.mark.parametrize('slope',[-1.,-.3,0.,.3,1.,3.])
def test_symmetric_wedge_is_one_analytic_circle_not_a_fixed_semicircle(slope):
    ps,ss=sides(slope,slope,1.)
    c=fit_circular_cap(ps,ss,True,[1,0]);radius=2*np.sqrt(1+slope*slope)
    assert c.ps_parameter==c.ss_parameter==0
    assert c.radius==pytest.approx(radius)
    np.testing.assert_allclose(c.center,[2*slope,0],atol=1e-12)
    assert abs(c.sweep)==pytest.approx(np.pi-2*np.arctan(slope))
    xy=c.sample(101)
    np.testing.assert_allclose(np.linalg.norm(xy-c.center,axis=1),radius,atol=1e-12)
    assert dot(c.direction(0),-ss.derivative(0))>1-1e-14
    assert dot(c.direction(1),ps.derivative(0))>1-1e-14


@pytest.mark.parametrize('slopes',[(.4,.1),(.1,.4),(-.1,-.4)])
def test_asymmetric_contact_moves_along_original_sides_and_stays_on_one_circle(slopes):
    ps,ss=sides(*slopes)
    c=fit_circular_cap(ps,ss,True,[1,0])
    assert min(c.ps_parameter,c.ss_parameter)==0
    assert 0<max(c.ps_parameter,c.ss_parameter)<MAX_CONTACT_FRACTION
    np.testing.assert_allclose(c.start,ss.evaluate(c.ss_parameter),atol=1e-12)
    np.testing.assert_allclose(c.end,ps.evaluate(c.ps_parameter),atol=1e-12)
    for side,u in ((ps,c.ps_parameter),(ss,c.ss_parameter)):
        assert abs(dot(side.evaluate(u)-c.center,side.derivative(u)))<1e-9
    np.testing.assert_allclose(np.linalg.norm(c.sample(101)-c.center,axis=1),c.radius,atol=1e-12)


@pytest.mark.parametrize('scale',[1e-4,1.,1e4])
@pytest.mark.parametrize('mirror',[-1.,1.])
def test_circle_contact_solution_preserves_rotation_translation_scale_and_reflection(scale,mirror):
    angle=.7;q=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])@np.diag([1.,mirror])
    ps,ss=sides(.4,.1);original=fit_circular_cap(ps,ss,True,[1,0]);offset=np.array([20.,-40.])*scale
    x=np.linspace(0,1,301)
    a=SampledSide(ps.evaluate(x)*scale@q+offset);b=SampledSide(ss.evaluate(x)*scale@q+offset)
    c=fit_circular_cap(a,b,True,np.array([1.,0.])@q)
    assert c.radius==pytest.approx(original.radius*scale,rel=2e-10)
    assert c.ps_parameter==pytest.approx(original.ps_parameter,abs=2e-10)
    assert c.ss_parameter==pytest.approx(original.ss_parameter,abs=2e-10)
    np.testing.assert_allclose(c.sample(31),original.sample(31)*scale@q+offset,atol=1e-9*scale)


def test_te_uses_last_region_and_correct_contour_orientation():
    ps,ss=sides(.4,.1);c=fit_circular_cap(ps,ss,False,[1,0])
    assert min(c.ps_parameter,c.ss_parameter)>=1-MAX_CONTACT_FRACTION
    np.testing.assert_allclose(c.start,ps.evaluate(c.ps_parameter),atol=1e-12)
    np.testing.assert_allclose(c.end,ss.evaluate(c.ss_parameter),atol=1e-12)
    assert dot(c.direction(0),ps.derivative(c.ps_parameter))>1-1e-9
    assert dot(c.direction(1),-ss.derivative(c.ss_parameter))>1-1e-9


def test_no_local_circle_is_refused_instead_of_using_two_arcs_or_extrapolation():
    x=np.linspace(0,1,101)
    ps=SampledSide(np.column_stack((x,2+x)));ss=SampledSide(np.column_stack((x,-2+x)))
    with pytest.raises(ValueError,match='single tangent circle'):fit_circular_cap(ps,ss,True,[1,0])


@pytest.mark.parametrize('xy',[[[0,0]],[[0,0],[1,np.nan],[2,0]],[[0,0,0]]*3])
def test_invalid_side_samples_fail(xy):
    with pytest.raises(ValueError):SampledSide(xy)


def select_arcs(p):
    for s in p.sections:s.edge_parameters.le_type=s.edge_parameters.te_type=EdgeType.TANGENT_CIRCULAR
    p.diffuser_profile.edge_parameters.le_type=p.diffuser_profile.edge_parameters.te_type=EdgeType.TANGENT_CIRCULAR
    return p


def join_cosines(s):
    def ends(c):
        spline=make_interp_spline(np.linspace(0,1,len(c.r)),c.xyz,k=3)
        return spline.derivative()(0),spline.derivative()(1)
    le,ps,te,ss=[ends(getattr(s,'master_'+n)) for n in ('le','ps','te','ss')]
    return [dot(le[1],ps[0]),dot(le[0],-ss[0]),dot(te[0],ps[1]),dot(te[1],-ss[1])]


def assert_single_chart_circle(s,role,rotation):
    curve=getattr(s,'master_'+role);index=0 if role=='le' else -1
    xy=np.column_stack((curve.meridional_distance,rotation*(curve.theta_rad-s.camber.theta_rad[index])*curve.r))
    a,b,c=xy[[0,len(xy)//2,-1]]
    center=np.linalg.solve(2*np.array([b-a,c-a]),np.array([np.dot(b-a,b-a),np.dot(c-a,c-a)]))+a
    radii=np.linalg.norm(xy-center,axis=1)
    assert np.ptp(radii)<2e-8


@pytest.mark.parametrize('rotation',list(RotationDirection))
@pytest.mark.parametrize('mapping',list(SurfaceMapping))
def test_main_splitter_contacts_keep_source_distributions_and_original_side_curves(rotation,mapping):
    p=radial_parameters();p.rotation_direction=rotation;p.surface_mapping=mapping
    for s in p.sections:
        s.edge_parameters.te_type=EdgeType.CIRCULAR
        s.thickness.points=[DistributionPoint(0,2),DistributionPoint(.4,5),DistributionPoint(1,1)]
    p.splitter=SplitterParameters();before=generate_impeller(p);select_arcs(p);original=deepcopy(p)
    after=generate_impeller(p);assert p==original
    for old_group,new_group in ((before.sections,after.sections),(before.splitter_sections,after.splitter_sections)):
        for old,new in zip(old_group,new_group):
            np.testing.assert_array_equal(old.camber.xyz,new.camber.xyz)
            np.testing.assert_array_equal(old.beta_m_deg,new.beta_m_deg)
            np.testing.assert_array_equal(old.thickness,new.thickness)
            for role in ('master_ps','master_ss'):
                a,b=getattr(old,role),getattr(new,role)
                spline=make_interp_spline(a.m_blade_norm,np.column_stack((a.meridional_distance,a.theta_rad)))
                np.testing.assert_allclose(np.column_stack((b.meridional_distance,b.theta_rad)),spline(b.m_blade_norm),atol=1e-11)
                assert b.m_blade_norm[0]>=a.m_blade_norm[0] and b.m_blade_norm[-1]<=a.m_blade_norm[-1]
            assert min(join_cosines(new))>1-2e-8
            for role in ('le','te'):assert_single_chart_circle(new,role,rotation.sign)


@pytest.mark.parametrize('rotation',list(RotationDirection))
def test_return_channel_inward_and_sharp_edges(rotation):
    p=select_arcs(return_channel_parameters());p.rotation_direction=rotation
    p.diffuser_profile.thickness.points=[DistributionPoint(0,2),DistributionPoint(.4,5),DistributionPoint(1,1)]
    assert all(min(join_cosines(s))>1-2e-8 for s in generate_diffuser_3d(p).sections)
    p.diffuser_profile.thickness.points[0].value=0
    for s in generate_diffuser_3d(p).sections:
        np.testing.assert_array_equal(s.master_le.xyz,np.repeat(s.master_le.xyz[:1],len(s.master_le.r),axis=0))


def test_2d_actual_side_interpolants_join_the_single_circles():
    from blade_designer.models.parameters import BladeParameters
    g=BladeDesigner().generate(select_arcs(BladeParameters()))
    def ends(side):
        spline=make_interp_spline(np.linspace(0,1,len(side.x)),side.xy)
        return spline.derivative()(0),spline.derivative()(1)
    le,ps,te,ss=[ends(getattr(g.master_surfaces,n)) for n in ('le','ps','te','ss')]
    assert min(dot(le[1],ps[0]),dot(le[0],-ss[0]),dot(te[0],ps[1]),dot(te[1],-ss[1]))>1-2e-8


def test_roundtrip_export_and_output_density_use_the_same_master(tmp_path):
    p=select_arcs(radial_parameters());p.export.significant_digits=15
    before=deepcopy(p);path=tmp_path/'tangent.json';save_project(path,p)
    restored=load_project(path);assert restored==p==before
    geometry=generate_impeller(restored);files=export_turbogrid(tmp_path/'case',restored);blocks=[]
    for line in files[2].read_text().splitlines():
        if line.startswith('#'):blocks.append([])
        else:blocks[-1].append([float(v) for v in line.split()[:3]])
    for rows,s in zip(blocks,geometry.sections):
        profile,markers=closed_profile(s);np.testing.assert_allclose(rows,profile,atol=1e-12,rtol=1e-14)
        assert set(markers.values())=={'le','te'}
    p.output_points.le_points=41;p.output_points.ps_points=51
    changed=generate_impeller(p)
    for a,b in zip(geometry.sections,changed.sections):
        for role in ('master_le','master_ps','master_te','master_ss'):
            np.testing.assert_array_equal(getattr(a,role).xyz,getattr(b,role).xyz)


def test_axial_clearance_and_cylindrical_cutoff_keep_their_geometry():
    from test_tip_clearance import axial_parameters
    from blade_designer.models.parameters import TipClearanceParameters
    p=select_arcs(axial_parameters());p.tip_clearance=TipClearanceParameters(.4,.8)
    g=generate_impeller(p);assert all(min(join_cosines(s))>1-2e-8 for s in g.sections)
    assert g.tip.clearance_mm.max()==pytest.approx(.8)
    p=radial_parameters()
    for section in p.sections:section.edge_parameters.le_type=EdgeType.TANGENT_CIRCULAR
    for s in generate_impeller(p).sections:
        assert np.all(s.master_te.r==120.)
        assert s.master_ps.r[-1]==s.master_ss.r[-1]==120.


def test_current_default_all_rows_have_valid_single_circle_edges_without_json_edits():
    import hashlib
    from pathlib import Path
    from blade_designer.models.blade_rows import row_parameters
    source=Path(__file__).parents[1]/'blade_designer/defaults/default_project.json'
    before=hashlib.sha256(source.read_bytes()).hexdigest();project=load_project(source)
    for row in project.blade_rows:
        p=select_arcs(row_parameters(project,row))
        g=(generate_impeller if row.kind=='impeller' else generate_diffuser_3d)(p)
        for sections in (g.sections,g.splitter_sections):
            if sections:
                assert all(min(join_cosines(s))>1-2e-8 for s in sections)
                for s in sections:
                    for role in ('le','te'):assert_single_chart_circle(s,role,p.rotation_direction.sign)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before


def test_solver_failure_protects_existing_exports_and_job(tmp_path,monkeypatch):
    from blade_designer.geometry import blade_section
    from blade_designer.cad.client import prepare_job
    p=radial_parameters();files=export_turbogrid(tmp_path/'case',p);original={f.name:f.read_bytes() for f in files}
    select_arcs(p)
    def failed(*args,**kwargs):raise ValueError('Injected tangent constraint failure')
    monkeypatch.setattr(blade_section,'fit_positioned_cap',failed)
    with pytest.raises(ValueError,match='tangent constraint'):export_turbogrid(tmp_path/'case',p)
    assert {f.name:f.read_bytes() for f in files}==original
    with pytest.raises(ValueError,match='tangent constraint'):export_turbogrid(tmp_path/'new',p)
    assert not (tmp_path/'new').exists()
    with pytest.raises(ValueError,match='tangent constraint'):prepare_job(p,'generate',tmp_path/'job')
    assert not (tmp_path/'job').exists()
