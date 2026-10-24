from copy import deepcopy
from dataclasses import replace
import math
import pytest

from blade_designer.models.parameters import BladeParameters, SplitterParameters
from blade_designer.models.blade_rows import initial_rows
from blade_designer.optimization.coordinate_parameters import CoordinateStudy, sample_candidates, _length
from blade_designer.geometry.meridional_segments import generate_meridional


@pytest.fixture
def project():
    p = BladeParameters()
    p.blade_rows = initial_rows(p)
    p.active_blade_row = p.blade_rows[0].identifier
    p.blade_rows[1].name = 'RC'
    return p


def key(study, row, group, index, name):
    return next(k for k, target in study._targets.items() if target == (row, group, index, name))


def test_neutral_migration_is_exact_and_baseline_owned(project):
    original = deepcopy(project)
    study = CoordinateStudy(project)
    assert study.candidate({v.key: 0. for v in study.variables}) == original
    project.blade_rows[0].name = 'changed'
    result = study.baseline
    result.hub.start_r = 123
    assert study.baseline == original


def test_beta_modes_on_original_controls_and_independent_rows(project):
    study = CoordinateStudy(project)
    row = project.blade_rows[0].identifier
    original = deepcopy(project)
    values = {key(study, row, 'main', 0, name): value
              for name, value in [('beta_le', 2.), ('beta_bow', 3.), ('beta_te', -1.)]}
    result = study.candidate(values)
    before = original.blade_rows[0].parameters.sections[0].blade_angle.points
    after = result.blade_rows[0].parameters.sections[0].blade_angle.points
    assert [p.m_norm for p in after] == [p.m_norm for p in before]
    assert after[0].value == before[0].value + 2
    assert after[-1].value == before[-1].value - 1
    assert after[2].value == before[2].value + .5 + 3
    assert result.blade_rows[0].parameters.sections[1] == original.blade_rows[0].parameters.sections[1]
    assert result.blade_rows[1] == original.blade_rows[1]
    assert project == original


def test_stator_changes_shared_profile_not_unused_rotor_sections(project):
    study = CoordinateStudy(project)
    row = project.blade_rows[1].identifier
    result = study.candidate({key(study, row, 'main', 0, 'beta_te'): 4.})
    assert result.blade_rows[1].parameters.diffuser_profile.blade_angle.points[-1].value == 54
    assert result.blade_rows[1].parameters.sections == project.blade_rows[1].parameters.sections


def test_thickness_endpoints_and_peak_warp(project):
    study = CoordinateStudy(project)
    row = project.blade_rows[0].identifier
    values = {key(study, row, 'main', 0, name): value for name, value in
              [('thickness_percent', 10.), ('peak_shift', .05), ('te_thickness', -.2)]}
    p = study.candidate(values).blade_rows[0].parameters.sections[0].thickness.points
    assert [x.value for x in p] == pytest.approx([1., 4.4, .8])
    assert [x.m_norm for x in p] == pytest.approx([0., .4, 1.])


@pytest.mark.parametrize('name,value', [('thickness_percent', -100.), ('peak_shift', 1.), ('le_thickness', -2.)])
def test_invalid_profile_changes_rejected_without_mutation(project, name, value):
    study = CoordinateStudy(project)
    before = study.baseline
    with pytest.raises(ValueError):
        study.candidate({key(study, project.active_blade_row, 'main', 0, name): value})
    assert study.baseline == before


def test_splitter_link_is_not_silently_converted(project):
    project.blade_rows[0].parameters.splitter = SplitterParameters()
    study = CoordinateStudy(project)
    assert not any(t[1] == 'splitter' for t in study._targets.values())
    assert study.candidate({}) == project


def test_dedicated_splitter_uses_only_active_interval(project):
    params = project.blade_rows[0].parameters
    params.splitter = SplitterParameters(sections=deepcopy(params.sections))
    study = CoordinateStudy(project)
    assert study.candidate({}) == project  # Neutral migration retains hidden legacy controls.
    result = study.candidate({key(study, project.active_blade_row, 'splitter', 0, 'beta_le'): 2.})
    points = result.blade_rows[0].parameters.splitter.sections[0].blade_angle.points
    assert points[0].m_norm == .5
    assert points[0].value == 60
    assert points[-1].value == 50


def test_arc_length_turn_and_g1_keep_topology(project):
    study = CoordinateStudy(project)
    arc = project.hub.segments[1]
    result = study.candidate({key(study, None, 'hub', 1, 'length_percent'): 10.,
                              key(study, None, 'hub', 1, 'turn_deg'): 5.})
    changed = result.hub.segments[1]
    assert changed.radius == pytest.approx(_length(arc) * 1.1 / math.radians(95))
    assert changed.sweep_deg == 95 and changed.clockwise == arc.clockwise
    geometry = generate_meridional(result.hub)
    for a, b in zip(geometry.segments, geometry.segments[1:]):
        assert a.end.zr == pytest.approx(b.start.zr)
        assert a.end_tangent == pytest.approx(b.start_tangent)
    assert len(result.hub.segments) == len(project.hub.segments)


def test_owned_wall_edge_positions_rebase_in_each_row_interval(project):
    first, second = project.blade_rows
    for wall in ('hub', 'shroud'):
        curve = getattr(project, wall)
        for index, segment in enumerate(curve.segments):
            segment.blade_row = first.identifier if index == 0 else second.identifier
        field = wall + '_m_flow_norm'
        for row, name, lo, hi in [(first, 'impeller_edges', .05, .15), (second, 'diffuser_edges', .5, .8)]:
            edges = getattr(row.parameters, name)
            setattr(edges.leading_edge, field, lo)
            setattr(edges.trailing_edge, field, hi)
    study = CoordinateStudy(project)
    result = study.candidate({key(study, None, 'hub', 0, 'length_percent'): 100.})
    old_total = sum(_length(s) for s in project.hub.segments)
    new_total = sum(_length(s) for s in result.hub.segments)
    leading = result.blade_rows[0].parameters.impeller_edges.leading_edge.hub_m_flow_norm
    assert leading * new_total / 50 == pytest.approx(.05 * old_total / 25)
    assert result.impeller_edges == result.blade_rows[0].parameters.impeller_edges


def test_invalid_assignment_cannot_be_hidden_by_wall_edit(project):
    for segment in project.hub.segments:
        segment.blade_row = project.active_blade_row
    study = CoordinateStudy(project)
    assert study.candidate({}) == project
    with pytest.raises(ValueError, match='assigned wall'):
        study.candidate({key(study, None, 'hub', 0, 'length_percent'): 1.})


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), '1'])
def test_bad_numbers_rejected(project, value):
    study = CoordinateStudy(project)
    with pytest.raises(ValueError):
        study.candidate({study.variables[0].key: value})


def test_sampling_bounds_reproducible_and_local_doe(project):
    study = CoordinateStudy(project)
    variable = replace(study.variables[0], enabled=True, lower=-4, upper=4)
    a = sample_candidates(study, [variable], 5, 43)
    assert a == sample_candidates(study, [variable], 5, 43) and a[0] == {}
    assert len({v[variable.key] for v in a[1:]}) == 5
    local = sample_candidates(study, [variable], 4, 43, {variable.key: 2})
    assert all(0 <= v[variable.key] <= 4 for v in local[1:])
    with pytest.raises(ValueError):
        sample_candidates(study, [variable, variable], 1)


@pytest.mark.parametrize('ids', [[], ['unknown'], ['row-1', 'row-1']])
def test_selection_rejected(project, ids):
    with pytest.raises(ValueError):
        CoordinateStudy(project, ids)


def test_linked_corrections_across_rows_share_one_lhs_dimension(project):
    study = CoordinateStudy(project)
    variables = [replace(next(v for v in study.variables
                             if study._targets[v.key] == (row.identifier, 'main', 0, 'beta_te')),
                         enabled=True, link='exit-angle', lower=-2, upper=3)
                 for row in project.blade_rows]
    samples = sample_candidates(study, variables, 4, 9)
    for values in samples[1:]:
        assert values[variables[0].key] == values[variables[1].key]
        study.check_vector(values, variables)
    bad = dict(samples[1])
    bad[variables[1].key] += .01
    with pytest.raises(ValueError, match='Linked'):
        study.check_vector(bad, variables)


def test_link_units_and_empty_intersection_rejected(project):
    study = CoordinateStudy(project)
    first = replace(study.variables[0], enabled=True, link='same')
    second = replace(study.variables[3], enabled=True, link='same')
    with pytest.raises(ValueError, match='same correction'):
        study.validate_variables([first, second])
    second = replace(next(v for v in study.variables if study._targets[v.key][2] == 1
                          and study._targets[v.key][-1] == 'beta_le'),
                     enabled=True, link='same', lower=6, upper=7)
    with pytest.raises(ValueError, match='common interval'):
        sample_candidates(study, [first, second], 1)
