import numpy as np
from blade_designer.models.parameters import BladeParameters, SurfaceMapping
from blade_designer.geometry.camber import generate_camber
from blade_designer.geometry.surface import generate_surfaces
from blade_designer.geometry.thickness import generate_thickness


def test_offsets_and_manual_mapping():
    p = BladeParameters()
    c = generate_camber(p)
    t = generate_thickness(c.m_norm,p.thickness)
    ps, ss, resolved, _ = generate_surfaces(c,t,SurfaceMapping.POSITIVE_IS_PS)
    for segment in (ps,ss):
        np.testing.assert_allclose(np.hypot(segment.x-c.x,segment.y-c.y),t/2)
    np.testing.assert_allclose((ps.xy+ss.xy)/2,np.column_stack((c.x,c.y)))
    a,b,_,_ = generate_surfaces(c,t,SurfaceMapping.NEGATIVE_IS_PS)
    np.testing.assert_allclose(a.xy,ss.xy)
    np.testing.assert_allclose(b.xy,ps.xy)
