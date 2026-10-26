"""Baseline-preserving coordinate-study variables. No Qt, CAD or surface checks."""
from copy import deepcopy
from dataclasses import dataclass
import json
import math

import numpy as np

from ..models.blade_rows import validate_rows
from ..models.meridional import ArcSegmentParameters
from ..geometry.meridional_segments import generate_meridional
from ..geometry.splitter import splitter_edit_points


@dataclass(frozen=True)
class CoordinateVariable:
    key: str
    label: str
    lower: float
    upper: float
    enabled: bool = False
    link: str = ''


def _key(*parts):
    return json.dumps(parts, ensure_ascii=False, separators=(',', ':'))


def _finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _length(segment):
    return (segment.radius * math.radians(abs(segment.sweep_deg))
            if isinstance(segment, ArcSegmentParameters) else segment.length)


def _interval(curve, identifier):
    indices = [i for i, segment in enumerate(curve.segments) if segment.blade_row == identifier]
    if not indices or indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError('Each affected row needs one continuous assigned wall interval.')
    lengths = [_length(segment) for segment in curve.segments]
    return sum(lengths[:indices[0]]), sum(lengths[i] for i in indices), sum(lengths)


class CoordinateStudy:
    """A frozen whole-project baseline; only explicitly selected rows get variables."""

    def __init__(self, project, row_ids=None):
        validate_rows(project)
        if not project.blade_rows:
            raise ValueError('Coordinate studies require a project with blade rows.')
        if any(row.independent_meridional for row in project.blade_rows):
            raise ValueError('Coordinate optimization of independent connected meridional elements is not supported yet.')
        self._baseline = deepcopy(project)
        known = [row.identifier for row in project.blade_rows]
        self.row_ids = tuple(known if row_ids is None else row_ids)
        if not self.row_ids or len(set(self.row_ids)) != len(self.row_ids) or set(self.row_ids) - set(known):
            raise ValueError('Select unique existing blade-row IDs.')
        self._targets = {}
        self.variables = []
        for row in project.blade_rows:
            if row.identifier not in self.row_ids:
                continue
            profiles = row.parameters.sections if row.kind == 'impeller' else [row.parameters.diffuser_profile]
            for index, profile in enumerate(profiles):
                self._profile_variables(row, 'main', index, profile)
            splitter = row.parameters.splitter if row.kind == 'impeller' else None
            if splitter is not None:
                for index, profile in enumerate(splitter.sections or []):
                    self._profile_variables(row, 'splitter', index, profile)
                for name, unit in (('hub_start_fraction', 'fraction'), ('tip_start_fraction', 'fraction'),
                                   ('pitch_fraction', 'pitch')):
                    self._add((row.identifier, 'splitter_setting', 0, name),
                              f'{row.name} / Splitter / Δ{name} [{unit}]', -.05, .05)
        for wall in ('hub', 'shroud'):
            curve = getattr(project, wall)
            for name in ('start_z', 'start_r', 'start_angle_deg'):
                self._add((None, wall, -1, name), f'Shared {wall} / Δ{name}', -5., 5.)
            for index, segment in enumerate(curve.segments):
                self._add((None, wall, index, 'length_percent'),
                          f'Shared {wall} / segment {index + 1} / Δlength [%]', -10., 10.)
                if isinstance(segment, ArcSegmentParameters):
                    bound = min(5., segment.sweep_deg * .25)
                    self._add((None, wall, index, 'turn_deg'),
                              f'Shared {wall} / segment {index + 1} / Δturn [deg]', -bound, bound)

    @property
    def baseline(self):
        return deepcopy(self._baseline)

    def _add(self, target, label, lower, upper, enabled=False):
        key = _key(*target)
        self._targets[key] = target
        self.variables.append(CoordinateVariable(key, label, lower, upper, enabled))

    def _profile_variables(self, row, group, index, profile):
        label = f'{row.name} / {group} / Span {profile.span:g}'
        for name in ('beta_le', 'beta_bow', 'beta_te'):
            self._add((row.identifier, group, index, name), f'{label} / Δ{name} [deg]', -5., 5., True)
        self._add((row.identifier, group, index, 'thickness_percent'),
                  f'{label} / interior thickness [%]', -10., 10.)
        self._add((row.identifier, group, index, 'peak_shift'),
                  f'{label} / thickness peak shift', -.05, .05)
        for side in ('le', 'te'):
            self._add((row.identifier, group, index, side + '_thickness'),
                      f'{label} / Δ{side} thickness [mm]', -.1, .1)

    def validate_variables(self, variables):
        seen = set()
        links = {}
        for variable in variables:
            if (not isinstance(variable, CoordinateVariable) or variable.key not in self._targets
                    or variable.key in seen or type(variable.enabled) is not bool
                    or not _finite(variable.lower) or not _finite(variable.upper)
                    or not variable.lower < variable.upper or not isinstance(variable.link, str)
                    or len(variable.link) > 128):
                raise ValueError('Invalid, duplicate or unknown coordinate-study variable.')
            seen.add(variable.key)
            if variable.enabled and variable.link:
                field = self._targets[variable.key][-1]
                if variable.link in links and links[variable.link] != field:
                    raise ValueError('Linked variables must represent the same correction and unit.')
                links[variable.link] = field
        return [v for v in variables if v.enabled]

    def check_vector(self, values, variables):
        active = self.validate_variables(variables)
        if (not isinstance(values, dict) or set(values) != {v.key for v in active}
                or any(not _finite(values[v.key]) or not v.lower <= values[v.key] <= v.upper for v in active)):
            raise ValueError('Candidate vector does not match its active variable bounds.')
        linked = {}
        for variable in active:
            if variable.link:
                value = values[variable.key]
                if variable.link in linked and linked[variable.link] != value:
                    raise ValueError('Linked corrections must have identical values.')
                linked[variable.link] = value

    def candidate(self, values):
        if not isinstance(values, dict) or set(values) - set(self._targets):
            raise ValueError('Unknown coordinate-study variable.')
        if not all(_finite(v) for v in values.values()):
            raise ValueError('Coordinate-study corrections must be finite physical numbers.')
        result = self.baseline
        profiles = {}
        wall_changes = {}
        modified_rows = set()
        rows = {row.identifier: row for row in result.blade_rows}
        for key, value in values.items():
            if value == 0:
                continue  # Exact neutral migration: no regridding or numeric round trip.
            identifier, group, index, name = self._targets[key]
            if identifier is None:
                wall_changes.setdefault((group, index), {})[name] = value
            elif group == 'splitter_setting':
                modified_rows.add(identifier)
                settings = rows[identifier].parameters.splitter
                setattr(settings, name, getattr(settings, name) + value)
            else:
                modified_rows.add(identifier)
                profiles.setdefault((identifier, group, index), {})[name] = value
        for (identifier, group, index), corrections in profiles.items():
            row = rows[identifier]
            parameters = row.parameters
            source = (parameters.splitter.sections if group == 'splitter'
                      else parameters.sections if row.kind == 'impeller' else [parameters.diffuser_profile])
            profile = source[index]
            start = 0.
            if group == 'splitter':
                settings = parameters.splitter
                start = (1 - profile.span) * settings.hub_start_fraction + profile.span * settings.tip_start_fraction
            self._correct_profile(profile, corrections, start)
        changed_walls = set()
        for (wall, index), corrections in wall_changes.items():
            curve = getattr(result, wall)
            if index == -1:
                for name, value in corrections.items():
                    setattr(curve, name, getattr(curve, name) + value)
            else:
                segment = curve.segments[index]
                length = _length(segment) * (1 + corrections.get('length_percent', 0) / 100)
                if length <= 0:
                    raise ValueError('Wall segment length must remain positive.')
                if isinstance(segment, ArcSegmentParameters):
                    angle = segment.sweep_deg + corrections.get('turn_deg', 0)
                    if angle <= 0:
                        raise ValueError('Arc turn must remain positive; topology and direction stay fixed.')
                    segment.radius = length / math.radians(angle)
                    segment.sweep_deg = angle
                else:
                    segment.length = length
            changed_walls.add(wall)
        for wall in changed_walls:
            generate_meridional(getattr(result, wall))
            self._rebase_edges(result, wall)
        if result.active_blade_row in modified_rows or changed_walls:
            from ..models.blade_rows import row_parameters, visible_edge_rows
            active = next(row for row in result.blade_rows if row.identifier == result.active_blade_row)
            synchronized = row_parameters(result, active)
            synchronized.blade_rows = result.blade_rows
            synchronized.active_blade_row = result.active_blade_row
            for name, row in visible_edge_rows(result.blade_rows, result.active_blade_row).items():
                setattr(synchronized, name, deepcopy(getattr(row.parameters, name)))
            result = synchronized
        # Shared values are resolved by row_parameters; snapshots retain their
        # prior unused shared fields, as in the ordinary project model.
        validate_rows(result)
        return result

    @staticmethod
    def _correct_profile(profile, corrections, start):
        if not 0 <= start < 1:
            raise ValueError('Splitter start must remain within [0,1).')
        angle_names = ('beta_le', 'beta_bow', 'beta_te')
        if any(corrections.get(name, 0) for name in angle_names):
            if start:
                profile.blade_angle.points = splitter_edit_points(profile.blade_angle.points, start)
            for point in profile.blade_angle.points:
                s = (point.m_norm - start) / (1 - start)
                point.value += ((1 - s) * corrections.get('beta_le', 0)
                                + s * corrections.get('beta_te', 0)
                                + 4 * s * (1 - s) * corrections.get('beta_bow', 0))
        thickness_names = ('thickness_percent', 'peak_shift', 'le_thickness', 'te_thickness')
        if not any(corrections.get(name, 0) for name in thickness_names):
            return
        points = splitter_edit_points(profile.thickness.points, start) if start else profile.thickness.points
        peak = max(points, key=lambda point: point.value).m_norm
        shift = corrections.get('peak_shift', 0) * (1 - start)
        target = peak + shift
        if shift and (not start < peak < 1 or not start < target < 1):
            raise ValueError('Peak shifting requires an interior baseline and target peak.')
        factor = 1 + corrections.get('thickness_percent', 0) / 100
        if factor <= 0:
            raise ValueError('Thickness multiplier must remain positive.')
        for i, point in enumerate(points):
            if i == 0:
                point.value += corrections.get('le_thickness', 0)
            elif i == len(points) - 1:
                point.value += corrections.get('te_thickness', 0)
            else:
                point.value *= factor
            if point.value < 0:
                raise ValueError('Negative thickness is not permitted.')
            if shift:
                x = point.m_norm
                point.m_blade_norm = (start + (x - start) * (target - start) / (peak - start)
                                     if x <= peak else target + (x - peak) * (1 - target) / (1 - peak))
        profile.thickness.points = points

    def _rebase_edges(self, result, wall):
        old, new = getattr(self._baseline, wall), getattr(result, wall)
        if not any(segment.blade_row is not None for segment in old.segments):
            return  # Legacy global-wall fractions stay unchanged.
        for source, row in zip(self._baseline.blade_rows, result.blade_rows):
            begin, length, total = _interval(old, row.identifier)
            new_begin, new_length, new_total = _interval(new, row.identifier)
            name = 'impeller_edges' if row.kind == 'impeller' else 'diffuser_edges'
            for side in ('leading_edge', 'trailing_edge'):
                old_edge = getattr(getattr(source.parameters, name), side)
                edge = getattr(getattr(row.parameters, name), side)
                field = wall + '_m_flow_norm'
                local = (getattr(old_edge, field) * total - begin) / length
                if not -1e-10 <= local <= 1 + 1e-10:
                    raise ValueError(f'{row.name}: LE/TE is outside its assigned {wall}; wall change rejected.')
                setattr(edge, field, (new_begin + local * new_length) / new_total)
        # The editor's top-level edge mirrors must follow the represented row.
        from ..models.blade_rows import visible_edge_rows
        for name, row in visible_edge_rows(result.blade_rows, result.active_blade_row).items():
            setattr(result, name, deepcopy(getattr(row.parameters, name)))


def sample_candidates(study, variables, count, seed=0, center=None):
    """Baseline plus bounded LHS. A subsequent batch may narrow around a chosen case."""
    from scipy.stats import qmc
    active = study.validate_variables(variables)
    if type(count) is not int or not 0 <= count <= 1000 or type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('Use 0..1000 samples and a nonnegative 32-bit integer seed.')
    if count and not active:
        raise ValueError('Enable at least one variable before sampling.')
    result = [{}]
    if not count:
        return result
    groups = {}
    for variable in active:
        group = ('link', variable.link) if variable.link else ('key', variable.key)
        groups.setdefault(group, []).append(variable)
    grouped = list(groups.values())
    lower = np.array([max(v.lower for v in group) for group in grouped])
    upper = np.array([min(v.upper for v in group) for group in grouped])
    if np.any(lower >= upper):
        raise ValueError('Linked variable bounds must have a nonempty common interval.')
    if center is not None:
        # Local DOE only, never advertised as surrogate/global optimization.
        if any(len({center.get(v.key, 0.) for v in group}) != 1 for group in grouped):
            raise ValueError('Local sampling center conflicts with the selected links.')
        midpoint = np.array([center.get(group[0].key, 0.) for group in grouped], dtype=float)
        if not np.isfinite(midpoint).all() or np.any(midpoint < lower) or np.any(midpoint > upper):
            raise ValueError('Local sampling center must lie inside the variable bounds.')
        width = (upper - lower) / 4
        lower, upper = np.maximum(lower, midpoint - width), np.minimum(upper, midpoint + width)
    values = qmc.scale(qmc.LatinHypercube(d=len(grouped), seed=seed).random(count), lower, upper)
    result.extend({v.key: float(value) for group, value in zip(grouped, vector) for v in group} for vector in values)
    return result
