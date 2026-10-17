"""Analytic spatial references, separate from historical 2D fixtures."""
from types import SimpleNamespace
import numpy as np
import pytest
from blade_designer.models.geometry_3d import Curve3D
from blade_designer.geometry.section_measurements import measure_section, spatial_curvature


def helix_section(n=1001, radius=50., slope=20.):
    t=np.linspace(0,1.2,n)
    def curve(r):return Curve3D(np.full(n,r),t,slope*t,t/1.2)
    return SimpleNamespace(span=.5,camber=curve(radius),master_ps=curve(radius-1),master_ss=curve(radius+1))


def test_helix_lengths_pitch_and_curvature_have_independent_analytic_references():
    section=helix_section();before=section.camber.xyz.copy()
    m=measure_section(section,20)
    assert m.camber_chord_xyz==pytest.approx(np.hypot(100*np.sin(.6),24),rel=1e-12)
    assert m.camber_length_xyz==pytest.approx(1.2*np.hypot(50,20),rel=1e-7)
    np.testing.assert_allclose(m.pitch,2*np.pi*50/20,rtol=1e-15)
    np.testing.assert_allclose(m.ps_curvature_xyz[3:-3],49/(49**2+20**2),rtol=2e-6)
    np.testing.assert_allclose(m.ss_curvature_xyz[3:-3],51/(51**2+20**2),rtol=2e-6)
    np.testing.assert_array_equal(section.camber.xyz,before)
    assert not np.shares_memory(m.radii,section.camber.r)


def test_helix_polyline_length_converges_and_is_not_xy_length():
    exact=1.2*np.hypot(50,20)
    coarse=measure_section(helix_section(51),11)
    fine=measure_section(helix_section(501),11)
    assert 0<exact-fine.camber_length_xyz<(exact-coarse.camber_length_xyz)/50
    assert fine.camber_length_xyz>50*1.2


def test_spatial_curvature_is_rigid_motion_invariant_and_scales_inversely():
    t=np.linspace(0,1.3,501)
    xyz=np.column_stack((40*np.cos(t),40*np.sin(t),12*t))
    rotation=np.array([[0,0,1],[1,0,0],[0,1,0]])
    k=spatial_curvature(xyz)
    np.testing.assert_allclose(spatial_curvature(xyz@rotation+np.array([8,4,-5])),k,rtol=1e-8)
    np.testing.assert_allclose(spatial_curvature(10*xyz),k/10,rtol=1e-8)


def test_straight_line_has_zero_spatial_curvature():
    t=np.linspace(0,1,51)
    xyz=np.column_stack((2*t+50,3*t,4*t))
    np.testing.assert_allclose(spatial_curvature(xyz),0,atol=1e-10)


@pytest.mark.parametrize('count',[True,0,-1,2.5])
def test_invalid_blade_count_is_rejected(count):
    with pytest.raises(ValueError,match='Blade count'):measure_section(helix_section(),count)


@pytest.mark.parametrize('points',[
    [[0,0,0],[0,0,0],[1,0,0]], [[0,0,0],[1,0,float('nan')],[2,0,0]], [[0,0],[1,1],[2,2]], [[0,0,0],[1,0,0]]])
def test_invalid_curvature_samples_are_rejected(points):
    with pytest.raises(ValueError):spatial_curvature(points)


def test_missing_or_nonincreasing_streamwise_coordinates_are_rejected():
    section=helix_section();section.master_ps.m_blade_norm=None
    with pytest.raises(ValueError,match='streamwise'):measure_section(section,20)
    section=helix_section();section.camber.m_blade_norm[10]=section.camber.m_blade_norm[9]
    with pytest.raises(ValueError,match='streamwise'):measure_section(section,20)
