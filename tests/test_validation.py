import pytest
from blade_designer.models.parameters import BladeParameters, DistributionPoint
from blade_designer.models.validation import validate_parameters, ValidationLevel


@pytest.mark.parametrize("group,name,value", [
    ("geometry","r_le",0), ("geometry","r_te",100), ("geometry","vane_count",0),
    ("geometry","vane_count",2.5), ("geometry","r_le",float("nan")),
    ("geometry","theta_le_deg",float("inf")), ("edges","le_ellipse_ratio",0),
    ("edges","te_ellipse_ratio",-1), ("edges","le_type","unknown"),
    ("output_points","ps_points",1), ("output_points","le_points",2.5),
    ("export","significant_digits",0), ("export","significant_digits",16),
    ("export","significant_digits",True), ("export","repeat_first_point",1),
])
def test_invalid(group, name, value):
    p = BladeParameters()
    setattr(getattr(p, group), name, value)
    assert any(i.level == ValidationLevel.ERROR for i in validate_parameters(p))


def test_default_and_warning():
    p, q = BladeParameters(), BladeParameters()
    assert validate_parameters(p) == []
    p.blade_angle.points[0].value = 81
    assert q.blade_angle.points[0].value == 65
    assert validate_parameters(p)[0].level == ValidationLevel.WARNING
