import numpy as np
from blade_designer.geometry import distributions, thickness
from blade_designer.models.parameters import ThicknessParameters


def test_shared_interpolator_and_monotone_no_overshoot(monkeypatch):
    calls = []
    original = distributions.interpolate_distribution
    def recording(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(distributions, "interpolate_distribution", recording)
    monkeypatch.setattr(thickness, "interpolate_distribution", recording)
    points = ThicknessParameters().points
    m_norm = np.linspace(0,1,2001)
    distributions.interpolate_beta_m_deg(m_norm,points)
    thickness.generate_thickness(m_norm,ThicknessParameters(points))
    assert len(calls) == 2
    control_m_norm = np.array([0,.25,.5,.75,1])
    values = np.array([0,1,2,2,3])
    np.testing.assert_allclose(original(control_m_norm,control_m_norm,values),values)
    result = original(m_norm,control_m_norm,values)
    assert np.all(np.diff(result) >= -1e-14)
    assert result.min() == 0 and result.max() == 3
