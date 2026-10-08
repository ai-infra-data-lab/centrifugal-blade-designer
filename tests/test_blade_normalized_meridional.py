import numpy as np
from copy import deepcopy
from blade_designer.models.parameters import BladeParameters,BladeSection
from blade_designer.models.blade_edge import BladeEdgePosition
from blade_designer.geometry.geometry_3d import generate_impeller

def test_each_section_normalizes_its_own_physical_interval():
    p=BladeParameters();p.sections.insert(1,BladeSection(.4))
    original=deepcopy(p.sections)
    p.impeller_edges.leading_edge=BladeEdgePosition(.2,.28)
    p.impeller_edges.trailing_edge=BladeEdgePosition(.72,.82)
    g=generate_impeller(p)
    for section in g.sections:
        np.testing.assert_allclose(section.camber.m_blade_norm,
            (section.m-section.m[0])/(section.m[-1]-section.m[0]),atol=1e-14)
        assert section.camber.m_blade_norm[0]==0 and section.camber.m_blade_norm[-1]==1
    assert p.sections==original
    assert g.sections[0].m[0]!=g.sections[-1].m[0]
