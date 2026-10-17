"""Inward-flow stator geometry, independent of the legacy outward 2D radii."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.geometry_3d import generate_diffuser_3d
from blade_designer.models.parameters import (BladeParameters,BladeAngleParameters,
    ThicknessParameters,DistributionPoint,EdgeType,RotationDirection)
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters


def return_channel_parameters(beta=20):
    p=BladeParameters()
    p.hub=MeridionalCurveParameters(0,160,-90,[LineSegmentParameters(100)])
    p.shroud=MeridionalCurveParameters(12,160,-90,[LineSegmentParameters(100)])
    for wall in ('hub','shroud'):
        setattr(p.diffuser_edges.leading_edge,wall+'_m_flow_norm',.2)
        setattr(p.diffuser_edges.trailing_edge,wall+'_m_flow_norm',.7)
    p.diffuser_profile.blade_angle=BladeAngleParameters([DistributionPoint(0,beta),DistributionPoint(1,beta)])
    p.diffuser_profile.thickness=ThicknessParameters([DistributionPoint(0,2),DistributionPoint(1,2)])
    return p


@pytest.mark.parametrize('rotation',list(RotationDirection))
@pytest.mark.parametrize('edge',list(EdgeType))
@pytest.mark.parametrize('beta',[-20,20])
def test_inward_meridional_flow_uses_positive_distance_and_correct_wrap(rotation,edge,beta):
    p=return_channel_parameters(beta);p.rotation_direction=rotation
    p.diffuser_profile.edge_parameters.te_type=edge
    original=deepcopy(p);g=generate_diffuser_3d(p);assert p==original
    assert [s.span for s in g.sections]==[0,1]
    for section in g.sections:
        c=section.camber
        np.testing.assert_allclose(c.r[[0,-1]],[140,90],atol=1e-12)
        assert np.all(np.diff(c.r)<0) and np.all(np.diff(c.meridional_distance)>0)
        expected=rotation.sign*np.tan(np.deg2rad(beta))*np.log(140/c.r)
        np.testing.assert_allclose(c.theta_rad,expected,atol=1e-8)
        np.testing.assert_allclose(c.z,12*section.span,atol=1e-12)
        for name in ('master_ps','master_ss','master_le','master_te'):
            assert np.isfinite(getattr(section,name).xyz).all()
        np.testing.assert_array_equal(section.master_le.xyz[-1],section.master_ps.xyz[0])
        np.testing.assert_array_equal(section.master_le.xyz[0],section.master_ss.xyz[0])
        np.testing.assert_array_equal(section.master_te.xyz[0],section.master_ps.xyz[-1])
        np.testing.assert_array_equal(section.master_te.xyz[-1],section.master_ss.xyz[-1])


def test_default_splitter_is_preserved_and_unsupported_impeller_export_is_protected(tmp_path):
    from pathlib import Path
    from blade_designer.fileio.project_io import load_project
    from blade_designer.models.blade_rows import row_parameters
    from blade_designer.fileio.turbogrid_export import export_turbogrid
    project=load_project(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json')
    p=row_parameters(project,project.blade_rows[0])
    p.blade_rows=deepcopy(project.blade_rows);p.active_blade_row='row-1'
    assert p.splitter is not None
    target=tmp_path/'case';target.mkdir();sentinel=target/'keep.txt';sentinel.write_bytes(b'original')
    with pytest.raises(ValueError,match='Splitter TurboGrid export is not supported'):
        export_turbogrid(target,p)
    assert list(target.iterdir())==[sentinel] and sentinel.read_bytes()==b'original'
