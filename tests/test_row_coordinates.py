"""Analytic row-owned wall length display; no geometry or schema changes."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.row_coordinates import build_row_coordinates
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters,ArcSegmentParameters


def curves():
    return [MeridionalCurveParameters(0,r,0,[LineSegmentParameters(a,'a'),ArcSegmentParameters(a,90,False,'a'),LineSegmentParameters(b,'b')])
            for r,a,b in ((50,10,50),(70,20,40))]


def test_analytic_line_arc_length_and_independent_wall_normalization():
    walls=curves();before=deepcopy(walls);c=build_row_coordinates(walls,['b','a'])
    assert c.order==('a','b') and walls==before
    for wall,a,b in (('hub',10,50),('shroud',20,40)):
        end=a*(1+np.pi/2);total=end+b
        assert c.position('a',wall,0)==0
        assert c.position('a',wall,end/total)==pytest.approx(1)
        assert c.position('b',wall,end/total)==pytest.approx(1)
        assert c.position('b',wall,1)==pytest.approx(2)
        assert c.position('b',wall,(end+.2*b)/total)==pytest.approx(1.2)
        assert c.position('b',wall,(end+.9*b)/total)==pytest.approx(1.9)
        assert c.segment_interval(wall,0)==pytest.approx((0,a/end))
        assert c.segment_interval(wall,1)==pytest.approx((a/end,1))
        assert c.segment_interval(wall,2)==pytest.approx((1,2))


def test_return_channel_follows_chain_direction_not_increasing_radius():
    walls=[MeridionalCurveParameters(0,200,-90,[LineSegmentParameters(10,'a'),LineSegmentParameters(20,'b'),LineSegmentParameters(30,'rc')]) for _ in range(2)]
    c=build_row_coordinates(walls,['rc','b','a'])
    assert c.order==('a','b','rc')
    assert c.position('rc','hub',.75)==pytest.approx(2.5)
    assert c.segment_interval('shroud',2)==(2.,3.)


def test_unowned_gap_has_no_coordinate_and_does_not_extend_a_row():
    walls=curves()
    for w in walls:w.segments.insert(2,LineSegmentParameters(7))
    c=build_row_coordinates(walls,['a','b'])
    assert c.segment_interval('hub',2) is None
    start,end=c.intervals['hub']['b']
    assert c.position('b','hub',start/c.boundaries['hub'][-1])==pytest.approx(1)
    assert end-start==pytest.approx(50)


def test_outside_owned_interval_is_reported_without_clamping():
    c=build_row_coordinates(curves(),['a','b'])
    assert c.position('a','hub',1)>1
    assert c.position('b','hub',0)<1


@pytest.mark.parametrize('problem',['missing','disconnected','order','unknown','duplicate','empty'])
def test_invalid_ownership_is_unavailable_instead_of_guessed(problem):
    walls=curves();ids=['a','b']
    if problem=='missing':walls[1].segments[-1].blade_row=None
    if problem=='disconnected':walls[0].segments.append(LineSegmentParameters(2,'a'))
    if problem=='order':
        for s in walls[1].segments:s.blade_row='b' if s.blade_row=='a' else 'a'
    if problem=='unknown':walls[0].segments[-1].blade_row='unknown'
    if problem=='duplicate':ids=['a','a']
    if problem=='empty':ids=[]
    with pytest.raises(ValueError):build_row_coordinates(walls,ids)


@pytest.mark.parametrize('bad',[0,-1,float('nan'),float('inf'),True])
def test_invalid_lengths_fail(bad):
    walls=curves();walls[0].segments[0].length=bad
    with pytest.raises(ValueError):build_row_coordinates(walls,['a','b'])


@pytest.mark.parametrize('bad',[0,-1,float('nan'),float('inf'),True,'20'])
def test_invalid_arc_radius_fails(bad):
    walls=curves();walls[0].segments[1].radius=bad
    with pytest.raises(ValueError):build_row_coordinates(walls,['a','b'])


@pytest.mark.parametrize('bad',[-.1,1.1,float('nan'),float('inf'),True,np.bool_(False)])
def test_invalid_global_wall_fraction_fails(bad):
    c=build_row_coordinates(curves(),['a','b'])
    with pytest.raises(ValueError):c.position('a','hub',bad)
