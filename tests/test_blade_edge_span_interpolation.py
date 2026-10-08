import numpy as np
from blade_designer.models.parameters import BladeParameters,BladeSection
from blade_designer.models.blade_edge import BladeEdgePosition
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.blade_edge import interpolate_edge_position

def test_unequal_endpoints_at_all_spans():
    p=BladeParameters();p.sections[1:1]=[BladeSection(.25),BladeSection(.5),BladeSection(.75)]
    p.impeller_edges.leading_edge=BladeEdgePosition(.2,.28)
    p.impeller_edges.trailing_edge=BladeEdgePosition(.72,.82)
    g=generate_impeller(p)
    for section in g.sections:
        for edge,index in ((p.impeller_edges.leading_edge,0),(p.impeller_edges.trailing_edge,-1)):
            np.testing.assert_allclose([section.camber.z[index],section.camber.r[index]],
                interpolate_edge_position(edge,g.hub,g.shroud,section.span),atol=2e-6)
