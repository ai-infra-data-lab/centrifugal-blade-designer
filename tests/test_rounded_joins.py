"""All rounded edge selections join the actual PS/SS; old data stays untouched."""
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from scipy.interpolate import make_interp_spline
from blade_designer.geometry.tangent_arcs import SampledSide,fit_circular_cap,fit_elliptical_cap
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.models.parameters import BladeParameters,EdgeType,RotationDirection
from blade_designer.models.blade_rows import row_parameters
from blade_designer.fileio.project_io import load_project,save_project
from test_tangent_arcs import dot,join_cosines


@pytest.mark.parametrize('ratio',[.5,1.,2.,4.])
@pytest.mark.parametrize('slope',[-.3,0.,.3])
@pytest.mark.parametrize('leading',[True,False])
def test_ellipse_has_analytic_axes_and_tangents_for_symmetric_wedge(ratio,slope,leading):
    x=np.linspace(0,1,301);b=2
    sides=[SampledSide(np.column_stack((x,sign*(b+slope*x)))) for sign in (1,-1)]
    cap=fit_elliptical_cap(*sides,leading,[1,0],ratio)
    c=cap.circle;xy=cap.sample(301);center=cap.origin+cap.inverse@c.center
    np.testing.assert_allclose(((xy[:,0]-center[0])/(ratio*c.radius))**2+((xy[:,1]-center[1])/c.radius)**2,1,atol=2e-12)
    if leading:
        assert c.radius==pytest.approx(b*np.sqrt(1+(slope*ratio)**2))
        assert center[0]==pytest.approx(b*slope*ratio**2,abs=1e-11)
    first,last=(sides[1],sides[0]) if leading else sides
    u0,u1=(cap.ss_parameter,cap.ps_parameter) if leading else (cap.ps_parameter,cap.ss_parameter)
    np.testing.assert_allclose(xy[0],first.evaluate(u0),atol=2e-12)
    np.testing.assert_allclose(xy[-1],last.evaluate(u1),atol=2e-12)
    assert dot(cap.direction(0),first.derivative(u0)*(-1 if leading else 1))>1-1e-12
    assert dot(cap.direction(1),last.derivative(u1)*(1 if leading else -1))>1-1e-12


@pytest.mark.parametrize('ratio',[.5,1.,3.])
@pytest.mark.parametrize('mirror',[-1,1])
def test_asymmetric_ellipse_contacts_survive_rigid_transform(ratio,mirror):
    x=np.linspace(0,100,301)
    ps=SampledSide(np.column_stack((x,2+.4*x)));ss=SampledSide(np.column_stack((x,-2-.1*x)))
    cap=fit_elliptical_cap(ps,ss,True,[1,0],ratio)
    angle=.7;q=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])@np.diag([1,mirror])
    offset=np.array([20.,-40.]);u=np.linspace(0,1,301)
    sides=[SampledSide(side.evaluate(u)@q+offset) for side in (ps,ss)]
    moved=fit_elliptical_cap(*sides,True,np.array([1.,0.])@q,ratio)
    np.testing.assert_allclose(moved.sample(31),cap.sample(31)@q+offset,atol=1e-10)
    assert max(cap.ps_parameter,cap.ss_parameter)>0
    if ratio==1:
        np.testing.assert_allclose(cap.sample(31),fit_circular_cap(ps,ss,True,[1,0]).sample(31),atol=1e-12)


@pytest.mark.parametrize('ratio',[0,-1,float('nan'),float('inf'),True,'2'])
def test_invalid_ellipse_ratio_is_explicit(ratio):
    x=np.linspace(0,1,31);a=SampledSide(np.column_stack((x,x+2)));b=SampledSide(np.column_stack((x,x-2)))
    with pytest.raises(ValueError,match='ratio'):fit_elliptical_cap(a,b,True,[1,0],ratio)


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL])
@pytest.mark.parametrize('rotation',list(RotationDirection))
def test_current_json_every_row_and_splitter_has_tangent_rounded_joins(kind,rotation,tmp_path):
    source=Path(__file__).parents[1]/'blade_designer/defaults/default_project.json'
    data=source.read_bytes();project=load_project(source)
    project.rotation_direction=rotation
    for row in project.blade_rows:
        p=row_parameters(project,row)
        for section in [*p.sections,p.diffuser_profile]:
            section.edge_parameters.le_type=section.edge_parameters.te_type=kind
            section.edge_parameters.le_ellipse_ratio=section.edge_parameters.te_ellipse_ratio=2.
        before=deepcopy(p);g=(generate_impeller if row.kind=='impeller' else generate_diffuser_3d)(p)
        assert p==before
        for group in (g.sections,g.splitter_sections):
            for section in group or []:assert min(join_cosines(section))>1-2e-8
        row.parameters=deepcopy(p)
    path=tmp_path/'all-rows.json';save_project(path,project);assert load_project(path)==project
    assert source.read_bytes()==data


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL])
def test_2d_regular_types_use_real_side_tangents_and_keep_source_distributions(kind):
    p=BladeParameters();p.edges.le_type=p.edges.te_type=kind
    p.edges.le_ellipse_ratio=p.edges.te_ellipse_ratio=2.
    before=deepcopy(p);g=BladeDesigner().generate(p);assert p==before
    def ends(side):return make_interp_spline(np.linspace(0,1,len(side.x)),side.xy).derivative()([0,1])
    le,ps,te,ss=[ends(getattr(g.master_surfaces,role)) for role in ('le','ps','te','ss')]
    assert min(dot(le[1],ps[0]),dot(le[0],-ss[0]),dot(te[0],ps[1]),dot(te[1],-ss[1]))>1-2e-8


def test_ellipse_failure_preserves_existing_export(tmp_path,monkeypatch):
    from blade_designer.fileio.turbogrid_export import export_turbogrid
    from blade_designer.geometry import blade_section
    from test_cylindrical_cutoff import radial_parameters
    p=radial_parameters();p.sections[0].edge_parameters.le_type=EdgeType.ELLIPTICAL
    files=export_turbogrid(tmp_path/'case',p);before={f.name:f.read_bytes() for f in files}
    def failed(*a,**k):raise ValueError('Injected ellipse tangent failure')
    monkeypatch.setattr(blade_section,'fit_positioned_cap',failed)
    with pytest.raises(ValueError,match='ellipse tangent'):export_turbogrid(tmp_path/'case',p)
    assert {f.name:f.read_bytes() for f in files}==before
    with pytest.raises(ValueError,match='ellipse tangent'):export_turbogrid(tmp_path/'new',p)
    assert not (tmp_path/'new').exists()
