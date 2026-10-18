from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.cad_surface_reference import join_surface_tangents,reference_surfaces,reference_lines
from blade_designer.geometry.surface_evaluation import fit_surface_spline
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.models.parameters import TipClearanceParameters,SplitterParameters
from test_cylindrical_cutoff import radial_parameters


@pytest.mark.parametrize('cutoff',[False,True])
def test_join_directions_match_independent_square_and_cutoff_exception(cutoff):
    rows={'le':[[0,0],[1,0]],'ps':[[1,0],[1,1]],'te':[[1,1],[0,1]],'ss':[[0,0],[0,1]]}
    payload=[{role:np.column_stack((points,np.full(2,z))) for role,points in rows.items()} for z in (0.,1.)]
    if cutoff:
        for row in payload:row['te_type']='cutoff'
    actual=join_surface_tangents(payload)
    diagonal=np.array([1.,1.,0.])/np.sqrt(2)
    np.testing.assert_allclose(actual['le'][1],[diagonal]*2,atol=1e-15)
    np.testing.assert_array_equal(actual['le'][1],actual['ps'][0])
    if cutoff:
        np.testing.assert_array_equal(actual['ps'][1],[[0,1,0]]*2)
        np.testing.assert_array_equal(actual['te'][0],[[-1,0,0]]*2)
    else:
        np.testing.assert_array_equal(actual['ps'][1],actual['te'][0])
        np.testing.assert_array_equal(actual['te'][1],-actual['ss'][1])


@pytest.mark.parametrize('density',[33,65,129,257,513])
def test_reference_factory_main_splitter_gap_rake_and_snapshot_are_stable(density):
    p=radial_parameters();p.impeller_te_rake_deg=12.;p.tip_clearance=TipClearanceParameters(.4,.8)
    p.splitter=SplitterParameters(sections=deepcopy(p.sections));before=deepcopy(p)
    geometry=generate_impeller(p)
    for sections in (geometry.sections,geometry.splitter_sections):
        original=[s.master_ps.xyz.copy() for s in sections]
        surfaces=reference_surfaces(sections,p.sections,density)
        assert set(surfaces)=={'le','ps','te','ss'}
        lines=reference_lines(surfaces,[s.span for s in sections])
        assert len(lines)==4*(21+len(sections))
        for s,xyz in zip(sections,original):np.testing.assert_array_equal(s.master_ps.xyz,xyz)
        np.testing.assert_allclose(lines['Hub ps'][0],surfaces['ps'].evaluate_grid([0],np.linspace(0,1,101))[0],atol=0,rtol=0)
    assert p==before


def test_reference_span_line_uses_cubic_surface_not_cartesian_chord():
    spans=np.array([0.,.2,.7,1.]);t=np.linspace(0,1,33)
    surface=fit_surface_spline([np.column_stack((t,np.full(len(t),s**3),np.full(len(t),s))) for s in spans],33,spans=spans)
    line=reference_lines({'ps':surface},[0.,1.])['Spanwise PS 50'][0]
    np.testing.assert_allclose(line[15],[.5,.125,.5],atol=1e-15)
    assert abs(line[15,1]-.5)>.3


@pytest.mark.parametrize('density',[0,1,True,'65'])
def test_invalid_density_is_not_silently_changed(density):
    p=radial_parameters();g=generate_impeller(p)
    with pytest.raises(ValueError):reference_surfaces(g.sections,p.sections,density)


def test_missing_profiles_is_not_silently_zipped():
    p=radial_parameters();g=generate_impeller(p)
    with pytest.raises(ValueError,match='count'):reference_surfaces(g.sections,p.sections[:1],65)
