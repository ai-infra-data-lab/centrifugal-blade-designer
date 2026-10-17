"""Validate serialized Profile Points without silently repairing design/output data."""
from copy import deepcopy
import hashlib
import pytest

from blade_designer.fileio.turbogrid_export import (
    export_turbogrid, closed_profile, _coordinates, _external_xyz,
    _validate_profile_coordinates,
)
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.span_extension import extend_tip_to_shroud
from blade_designer.models.parameters import BladeParameters, EdgeType, TipClearanceParameters
from test_impeller_te_rake import radial_parameters


@pytest.fixture(scope='module')
def reference_profiles():
    cases={}
    for edge in EdgeType:
        for gap in (False,True):
            params=radial_parameters(edge)
            if gap:params.tip_clearance=TipClearanceParameters(1.,2.)
            geometry=generate_impeller(params)
            sections=[*geometry.sections]
            if gap:sections.append(extend_tip_to_shroud(geometry))
            cases[edge,gap]=[closed_profile(section) for section in sections]
    return cases


@pytest.mark.parametrize('axis',['X','Y','Z'])
@pytest.mark.parametrize('unit',['MM','CM','M'])
@pytest.mark.parametrize('edge',list(EdgeType))
@pytest.mark.parametrize('gap',[False,True])
def test_all_precisions_units_axes_edges_and_clearance(reference_profiles,axis,unit,edge,gap):
    settings=BladeParameters().turbogrid
    settings.rotation_axis=axis;settings.geometry_unit=unit
    for digits in range(1,16):
        for xyz,markers in reference_profiles[edge,gap]:
            coordinates=_coordinates(_external_xyz(xyz,settings),digits,markers)
            rows=[line.split() for line in coordinates.splitlines()]
            vertices=[tuple(map(float,row[:3])) for row in rows]
            # A format-level oracle: actual adjacent vertices and marked vertices
            # must survive rounding. No expected geometry values are replaced.
            duplicate=any(a==b for a,b in zip(vertices,vertices[1:]))
            same_edge=vertices[next(i for i,n in markers.items() if n=='le')]==vertices[next(i for i,n in markers.items() if n=='te')]
            if duplicate or same_edge:
                with pytest.raises(ValueError,match='precision'):
                    _validate_profile_coordinates(coordinates)
            else:
                assert _validate_profile_coordinates(coordinates)==len(xyz)
                assert vertices[0]==vertices[-1]
                assert [row[3] for row in rows if len(row)==4].count('le')==1
                assert [row[3] for row in rows if len(row)==4].count('te')==1
            if digits==1:assert duplicate  # the audit's invalid precision case
            if digits>=8:assert not duplicate and not same_edge


@pytest.mark.parametrize('invalid',[
    '', '0 0 0 le\n1 0 0 te\n0 1 0\n',
    '0 0 0 le\n1 0 0 te\n1 0 0\n0 0 0\n',
    '0 0 0 le\n1 0 0\n0 1 0\n0 0 0\n',
    '0 0 0 le\n1 0 0 le\n0 1 0 te\n0 0 0\n',
    '0 0 0 le\n1 0 0\n0 0 0 te\n0 1 0\n0 0 0\n',
    '0 0 0 le\n1 0 0 te\n0 1 0\n0 0 0 extra\n',
    '0 0 0 le\ninf 0 0 te\n0 1 0\n0 0 0\n',
])
def test_corrupt_contour_or_markers_rejected(invalid):
    with pytest.raises(ValueError):_validate_profile_coordinates(invalid)


def test_low_precision_main_only_rejected_before_touching_existing_case(tmp_path):
    params=BladeParameters()
    files=export_turbogrid(tmp_path/'existing',params)
    saved={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    params.export.significant_digits=1;before=deepcopy(params)
    for target in (tmp_path/'existing',tmp_path/'new'):
        with pytest.raises(ValueError,match='precision'):export_turbogrid(target,params)
    assert not (tmp_path/'new').exists()
    assert {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}==saved
    assert params==before


def test_main_only_requires_matching_span_contour_counts_before_publish(tmp_path):
    params=BladeParameters()
    files=export_turbogrid(tmp_path/'existing',params)
    saved={path:path.read_bytes() for path in files}
    # A sharp LE at only one span changes the number of distinct contour nodes.
    params.sections[-1].thickness.points[0].value=0
    for target in (tmp_path/'existing',tmp_path/'new'):
        with pytest.raises(ValueError,match='matching'):export_turbogrid(target,params)
    assert not (tmp_path/'new').exists()
    assert all(path.read_bytes()==data for path,data in saved.items())
