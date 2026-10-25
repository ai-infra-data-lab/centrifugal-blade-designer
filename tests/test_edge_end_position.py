"""Completed rounded noses, rather than camber ends, own meridional LE/TE."""
from copy import deepcopy
import numpy as np
import pytest

from blade_designer.geometry.blade_section import generate_section
from blade_designer.models.parameters import (BladeSection, DistributionPoint, EdgeType,
    OutputPointParameters, SurfaceMapping)
from blade_designer.models.resolution import GeometryResolutionParameters


def profile(kind, beta=0., thickness=2.):
    section=BladeSection(0.)
    section.blade_angle.points=[DistributionPoint(0.,beta),DistributionPoint(1.,beta)]
    section.thickness.points=[DistributionPoint(0.,thickness),DistributionPoint(1.,thickness)]
    section.edge_parameters.le_type=section.edge_parameters.te_type=kind
    section.edge_parameters.le_ellipse_ratio=section.edge_parameters.te_ellipse_ratio=2.
    return section


def generate(section, *, fractions=(.2,.8), direction=1, axis='axial', edge_points=401, output=21):
    q=np.linspace(0.,100.,501)
    wall=np.column_stack((q,np.full(len(q),100.))) if axis=='axial' else np.column_stack((q*0,160.-q))
    return generate_section(section,wall,*fractions,0.,OutputPointParameters(output,101,output,101),
                            SurfaceMapping.POSITIVE_IS_PS,
                            GeometryResolutionParameters(profile_points=501,edge_points=edge_points),
                            rotation_sign=direction)


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL,EdgeType.TANGENT_CIRCULAR])
def test_constant_axial_profile_matches_analytic_nose_and_preserves_camber(kind):
    design=profile(kind);before=deepcopy(design)
    section=generate(design)
    radius=2. if kind==EdgeType.ELLIPTICAL else 1.
    np.testing.assert_allclose(section.m[[0,-1]],[20,80],atol=2e-9)
    assert section.master_ps.meridional_distance[0]==pytest.approx(20+radius,abs=2e-9)
    assert section.master_ps.meridional_distance[-1]==pytest.approx(80-radius,abs=2e-9)
    for curve,expected,extreme in ((section.master_le,20.,np.argmin),(section.le,20.,np.argmin),
                                   (section.master_te,80.,np.argmax),(section.te,80.,np.argmax)):
        index=extreme(curve.meridional_distance)
        np.testing.assert_allclose([curve.z[index],curve.r[index]],[expected,100.],atol=2e-9)
    assert design==before


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL])
@pytest.mark.parametrize('beta',[-35.,35.])
@pytest.mark.parametrize('axis',['axial','inward'])
@pytest.mark.parametrize('direction',[-1,1])
def test_asymmetric_caps_and_sparse_exports_retain_positions(kind,beta,axis,direction):
    section=generate(profile(kind,beta),axis=axis,direction=direction,edge_points=100,output=8)
    for name,target,extreme in (('le',20.,np.min),('te',80.,np.max)):
        for prefix in ('','master_'):
            curve=getattr(section,prefix+name)
            assert extreme(curve.meridional_distance)==pytest.approx(target,abs=2e-9)
            expected=target if axis=='axial' else 160.-target
            values=curve.z if axis=='axial' else curve.r
            assert np.min(np.abs(values-expected))<2e-9
    for name in ('master_ps','master_ss','master_le','master_te'):
        distance=getattr(section,name).meridional_distance
        assert distance.min()>=20.-2e-9 and distance.max()<=80.+2e-9
    assert len(section.master_le.r)==100 and len(section.le.r)==8


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL])
def test_noses_can_be_at_finite_wall_ends_without_publishing_extrapolation(kind):
    section=generate(profile(kind),fractions=(0.,1.))
    assert section.master_le.meridional_distance.min()==pytest.approx(0.,abs=2e-9)
    assert section.master_te.meridional_distance.max()==pytest.approx(100.,abs=2e-9)


def test_no_room_for_thick_caps_is_an_explicit_error():
    with pytest.raises(ValueError,match='positioning|overlap|self intersection|single tangent'):
        generate(profile(EdgeType.ELLIPTICAL,thickness=40.))


def test_cylinder_cut_sides_keep_analytic_constant_beta_through_extended_endpoint():
    # On R=50+m, constant beta integrates to tan(beta)*log(R/R_LE).
    # A finite-thickness normal offset shifts m, not its sampling parameter.
    # One cylinder-cut endpoint is extended by much more than an interior step.
    design=profile(EdgeType.CIRCULAR,beta=60.,thickness=4.)
    design.edge_parameters.te_type=EdgeType.CUTOFF
    wall=np.column_stack((np.zeros(501),np.linspace(50.,150.,501)))
    section=generate_section(design,wall,.2,.8,0.,OutputPointParameters(),
        SurfaceMapping.POSITIVE_IS_PS,GeometryResolutionParameters(profile_points=501),
        cutoff_radius=130.)
    beta=np.deg2rad(60.);dm=-2*np.sin(beta);dy=2*np.cos(beta)
    for side,curve in ((1,section.master_ps),(-1,section.master_ss)):
        camber_m=curve.meridional_distance-side*dm
        expected=np.tan(beta)*np.log((50.+camber_m)/70.)+side*dy/curve.r
        np.testing.assert_allclose(curve.theta_rad,expected,rtol=0,atol=5e-7)
        assert curve.r[-1]==130.


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL])
def test_two_output_points_cannot_silently_drop_the_nose(kind):
    with pytest.raises(ValueError,match='at least three output points'):
        generate(profile(kind),output=2)
    section=generate(profile(kind),output=3)
    assert section.le.meridional_distance[1]==pytest.approx(20.,abs=2e-9)
    assert section.te.meridional_distance[1]==pytest.approx(80.,abs=2e-9)


def test_two_point_cutoff_remains_a_straight_join():
    section=generate(profile(EdgeType.CUTOFF),output=2)
    assert len(section.le.r)==len(section.te.r)==2
    np.testing.assert_array_equal(section.le.xyz[0],section.ss.xyz[0])
    np.testing.assert_array_equal(section.le.xyz[-1],section.ps.xyz[0])


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL])
@pytest.mark.parametrize('beta',[-75.,35.,75.])
def test_nose_sampling_has_no_parameter_speed_jump(kind,beta):
    errors=[]
    for count in (401,1601):
        section=generate(profile(kind,beta),edge_points=count)
        row=[]
        for role in ('le','te'):
            curve=getattr(section,'master_'+role);middle=len(curve.r)//2
            lengths=np.linalg.norm(np.diff(curve.xyz,axis=0),axis=1)
            assert np.all(lengths>0)
            row.append(abs(lengths[middle]/lengths[middle-1]-1))
        errors.append(np.array(row))
    # A C1 map converges to the same one-sided speed as spacing decreases;
    # the former piecewise-linear parameterization retains a finite jump.
    assert np.all(errors[1]<.4*errors[0]+1e-8)


def test_default_cad_reference_meets_unchanged_tolerance_with_original_density_limit():
    from pathlib import Path
    from blade_designer.fileio.project_io import load_project
    from blade_designer.models.blade_rows import row_parameters
    from blade_designer.geometry.geometry_3d import generate_impeller
    from blade_designer.geometry.cad_surface_reference import reference_surfaces
    from blade_designer.geometry.surface_correspondence import cad_curve_coordinates
    project=load_project(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json')
    params=row_parameters(project,project.blade_rows[0]);before=deepcopy(params)
    geometry=generate_impeller(params)
    for group in (geometry.sections,geometry.splitter_sections):
        if not group:continue
        surfaces=reference_surfaces(group,params.sections,{'le':65,'ps':257,'te':33,'ss':257})
        for section in group:
            for role,surface in surfaces.items():
                curve=getattr(section,'master_'+role)
                points=surface.evaluate_grid([section.span],cad_curve_coordinates(curve))[0]
                assert np.max(np.linalg.norm(points-curve.xyz,axis=1))<=params.cad_export.surface_tolerance_mm
    assert params==before


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL])
def test_export_marker_midpoints_are_the_positioned_noses(kind):
    from blade_designer.fileio.turbogrid_export import closed_profile
    from blade_designer.geometry.surface_correspondence import display_master_coordinates
    section=generate(profile(kind,35.),output=9)
    points,markers=closed_profile(section)
    for index,role in markers.items():
        assert points[index,2]==pytest.approx(20. if role=='le' else 80.,abs=2e-9)
    for role in ('le','te'):
        master,display=getattr(section,'master_'+role),getattr(section,role)
        coordinates=display_master_coordinates(master,display)
        assert np.all(np.diff(coordinates)>0)
        assert len(coordinates)==len(display.r)


@pytest.mark.parametrize('kind',[EdgeType.CIRCULAR,EdgeType.ELLIPTICAL])
def test_default_all_rows_and_splitters_have_the_reference_rz_at_finished_noses(kind):
    from pathlib import Path
    from blade_designer.fileio.project_io import load_project
    from blade_designer.models.blade_rows import row_parameters
    from blade_designer.models.parameters import ImpellerTrimParameters
    from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
    source=Path(__file__).parents[1]/'blade_designer/defaults/default_project.json'
    original=source.read_bytes();project=load_project(source)
    for row in project.blade_rows:
        params=row_parameters(project,row)
        params.impeller_trim=ImpellerTrimParameters()
        for section in [*params.sections,params.diffuser_profile]:
            section.edge_parameters.le_type=section.edge_parameters.te_type=kind
            section.edge_parameters.le_ellipse_ratio=section.edge_parameters.te_ellipse_ratio=2.
        before=deepcopy(params)
        geometry=(generate_impeller if row.kind=='impeller' else generate_diffuser_3d)(params)
        for group in (geometry.sections,geometry.splitter_sections):
            for section in group or []:
                for role,index in (('le',0),('te',-1)):
                    target=[section.camber.r[index],section.camber.z[index]]
                    for prefix in ('master_',''):
                        curve=getattr(section,prefix+role);nose=len(curve.r)//2
                        np.testing.assert_allclose([curve.r[nose],curve.z[nose]],target,rtol=0,atol=2e-9)
        assert params==before
    assert source.read_bytes()==original
