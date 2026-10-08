import pytest
from blade_designer.models.parameters import DistributionPoint
from blade_designer.models.validation import validate_control_points, ValidationLevel


@pytest.mark.parametrize("points,kind", [
    ([], "blade_angle"), ([(0,20)], "blade_angle"),
    ([(.1,20),(1,30)],"blade_angle"), ([(0,20),(.5,30),(.5,40),(1,50)],"blade_angle"),
    ([(0,20),(.7,30),(.4,40),(1,50)],"blade_angle"),
    ([(0,85),(1,30)],"blade_angle"), ([(0,-85),(1,30)],"blade_angle"),
    ([(0,1),(1,-1)],"thickness"), ([(0,1),(1,float("nan"))],"thickness"),
])
def test_invalid_control_points(points, kind):
    assert any(i.level == ValidationLevel.ERROR for i in validate_control_points([DistributionPoint(*p) for p in points], kind))


def test_arbitrary_count():
    points = [DistributionPoint(i/8, 20+i) for i in range(9)]
    assert validate_control_points(points, "blade_angle") == []
