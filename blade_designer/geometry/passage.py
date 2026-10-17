"""Passage cuts and section-to-section throat estimates from master geometry.

Area: normal cuts of the mean meridional line, circumferential arc gaps,
trapezoidal integration over the existing span sections. Throat: closest
master-polyline connectors per section, then a Hub–Tip width integral.
The latter is an estimate, not a globally minimal 3-D stream-normal surface.
No Qt, CAD, export resampling, or parameter mutation.
"""
import numpy as np
from scipy.spatial import cKDTree
from ..models.passage import PassageAreaStation, PassageThroat, PassageResult
from .flow_area import calculate_flow_area


def _contour(section):
    curves = (section.master_le, section.master_ps, section.master_te)
    points = np.concatenate([c.xyz[:-1] for c in curves] + [section.master_ss.xyz[::-1][:-1]])
    if len(points) < 3 or not np.isfinite(points).all():
        raise ValueError("Finite closed master contours are required.")
    return np.vstack((points, points[0]))


def _rotate(points, angle):
    c, s = np.cos(angle), np.sin(angle)
    return points @ np.array([[c, s, 0.], [-s, c, 0.], [0., 0., 1.]])


def _segment_pairs(a, b, c, d):
    """Exact closest points of corresponding closed line-segment pairs."""
    u, v, w = b-a, d-c, a-c
    uu = np.einsum('ij,ij->i', u, u)
    vv = np.einsum('ij,ij->i', v, v)
    uv = np.einsum('ij,ij->i', u, v)
    uw = np.einsum('ij,ij->i', u, w)
    vw = np.einsum('ij,ij->i', v, w)
    candidates = []
    for p in (a, b):
        t = np.clip(np.einsum('ij,ij->i', p-c, v)/np.maximum(vv, 1e-300), 0, 1)
        candidates.append((p, c+t[:, None]*v))
    for q in (c, d):
        t = np.clip(np.einsum('ij,ij->i', q-a, u)/np.maximum(uu, 1e-300), 0, 1)
        candidates.append((a+t[:, None]*u, q))
    determinant = uu*vv-uv*uv
    safe = determinant > 1e-12*uu*vv
    s = np.divide(uv*vw-vv*uw, determinant, out=np.zeros_like(uu), where=safe)
    t = np.divide(uu*vw-uv*uw, determinant, out=np.zeros_like(uu), where=safe)
    valid = safe & (s >= 0) & (s <= 1) & (t >= 0) & (t <= 1)
    p, q = a+s[:, None]*u, c+t[:, None]*v
    distances = np.where(valid, np.linalg.norm(p-q, axis=1), np.inf)
    best = int(np.argmin(distances))
    result = (distances[best], p[best], q[best])
    for p, q in candidates:
        distances = np.linalg.norm(p-q, axis=1)
        best = int(np.argmin(distances))
        if distances[best] < result[0]:
            result = (distances[best], p[best], q[best])
    return result


def closest_polylines(first, second):
    """Global minimum on the supplied polylines, with conservative KD bounds."""
    first, second = np.asarray(first), np.asarray(second)
    if any(p.ndim != 2 or p.shape[1] != 3 or len(p) < 2 or not np.isfinite(p).all()
           for p in (first, second)):
        raise ValueError("Finite XYZ polylines with at least two vertices are required.")
    distance, nearest = cKDTree(second).query(first)
    index = int(np.argmin(distance))
    best = (float(distance[index]), first[index].copy(), second[nearest[index]].copy())
    centers = (second[:-1]+second[1:])/2
    half = np.linalg.norm(np.diff(second, axis=0), axis=1)/2
    max_half = float(max(half))
    tree = cKDTree(centers)
    # A segment closer than the vertex upper bound must have centers within
    # upper_bound + both half-lengths. Never prune merely by nearest vertices.
    for a, b in zip(first[:-1], first[1:]):
        center = (a+b)/2
        ids = np.asarray(tree.query_ball_point(center, best[0]+np.linalg.norm(b-a)/2+max_half), dtype=int)
        if not len(ids):
            continue
        result = _segment_pairs(np.broadcast_to(a, (len(ids), 3)), np.broadcast_to(b, (len(ids), 3)),
                                second[ids], second[ids+1])
        if result[0] < best[0]:
            best = result
    return best


def _section_gap(first, second, angle):
    a, b = _contour(first), _rotate(_contour(second), angle)
    # For a straight meridional generator, unfold the cylinder/cone exactly.
    # In particular, a cylinder's chord would cut into the Hub solid: use its
    # circumferential arc distance instead. Radial planes are the k=1 case.
    origin = np.array([first.camber.z[0], first.camber.r[0]])
    delta = np.array([first.camber.z[-1], first.camber.r[-1]])-origin
    length = np.linalg.norm(delta)
    tangent = delta/max(length, 1e-300)
    k = tangent[1]
    zrs = np.concatenate([np.column_stack((c.z, c.r)) for section in (first, second)
                          for c in (section.master_le, section.master_ps, section.master_te, section.master_ss)])
    normal = np.array([-tangent[1], tangent[0]])
    if length < 1e-10 or np.max(np.abs((zrs-origin) @ normal)) > 1e-7:
        return (*closest_polylines(a, b), 'Curved wall: XYZ chord lower-bound estimate')
    anchor = float(np.mean(first.camber.theta_rad))
    def unfold(points, theta):
        r = np.hypot(points[:, 0], points[:, 1])
        zr = np.column_stack((points[:, 2], r))
        if abs(k) < 1e-9:
            return np.column_stack(((zr-origin) @ tangent, r*(theta-anchor), np.zeros(len(r))))
        phi = abs(k)*(theta-anchor)
        return np.column_stack((r/abs(k)*np.cos(phi), r/abs(k)*np.sin(phi), np.zeros(len(r))))
    def angles(section):
        return np.r_[section.master_le.theta_rad[:-1], section.master_ps.theta_rad[:-1],
                     section.master_te.theta_rad[:-1], section.master_ss.theta_rad[::-1][:-1],
                     section.master_le.theta_rad[0]]
    ta, tb = angles(first), angles(second)+angle
    if np.max(np.abs(np.r_[ta, tb]-anchor)) >= np.pi:
        raise ValueError('Multi-turn blade wrap: unique throat development unavailable.')
    width, p, q = closest_polylines(unfold(a, ta), unfold(b, tb))
    def fold(point):
        if abs(k) < 1e-9:
            zr = origin+point[0]*tangent
            theta = point[1]/zr[1]+anchor
        else:
            r = np.hypot(point[0], point[1])*abs(k)
            zr = origin+(r-origin[1])/k*tangent
            theta = np.arctan2(point[1], point[0])/abs(k)+anchor
        return np.array([zr[1]*np.cos(theta), zr[1]*np.sin(theta), zr[0]])
    return width, fold(p), fold(q), 'Developed cylinder/cone (master polylines)'


def _throat(name, first, second, angle, reference=False):
    values = [_section_gap(a, b, angle) for a, b in zip(first, second)]
    widths = np.array([v[0] for v in values])
    if np.min(widths) <= 1e-8:
        raise ValueError(f"{name}: touching/intersecting section contours; throat unavailable.")
    a, b = np.array([v[1] for v in values]), np.array([v[2] for v in values])
    # Integrate widths along the meridional midpoint locus. A Cartesian ruled
    # strip would replace a cylindrical arc by a chord and undercount its area.
    # This is still an estimate: each span minimum can occur at a different m.
    centers = np.column_stack(((a[:, 2]+b[:, 2])/2,
                               (np.hypot(a[:, 0], a[:, 1])+np.hypot(b[:, 0], b[:, 1]))/2))
    distances = np.linalg.norm(np.diff(centers, axis=0), axis=1)
    if np.any(distances <= 1e-10):
        raise ValueError(f"{name}: collapsed span connectors; throat area unavailable.")
    areas = (widths[:-1]+widths[1:])/2*distances
    methods = sorted({v[3] for v in values})
    return PassageThroat(name, np.array([s.span for s in first]), widths, a, b, float(sum(areas)), reference, '; '.join(methods))


def _hits(curve, mean, tangent):
    """Intersections in the (Z,R,theta) master chart, not an XY projection."""
    zr = np.column_stack((curve.z, curve.r))
    f = (zr-mean) @ tangent
    hit = np.flatnonzero((f[:-1]*f[1:] <= 0) & (np.abs(f[1:]-f[:-1]) > 1e-12))
    values = []
    for i in hit:
        t = -f[i]/(f[i+1]-f[i])
        values.append(np.r_[zr[i]+t*(zr[i+1]-zr[i]),
                            curve.theta_rad[i]+t*(curve.theta_rad[i+1]-curve.theta_rad[i])])
    # Entirely coincident edges (e.g. a cylindrical TE cap) contribute both ends.
    near = np.abs(f) <= 1e-10
    ends = near & ~(np.r_[False, near[:-1]] & np.r_[near[1:], False])
    values.extend(np.c_[zr[ends], curve.theta_rad[ends]])
    if not values:
        return np.empty((0, 3))
    return np.unique(np.round(values, 10), axis=0)


def _interval(section, mean, tangent, sign):
    hits = [_hits(getattr(section, 'master_'+n), mean, tangent) for n in ('le', 'ps', 'te', 'ss')]
    hits = np.concatenate(hits)
    if not len(hits):
        return None
    theta = sign*hits[:, 2]
    # A multi-valued cut through a folded profile cannot be represented by one
    # blocked interval. Refuse it instead of filling holes with a min/max hull.
    distinct = np.unique(np.round(theta, 9))
    if len(distinct) > 2:
        raise ValueError("Ambiguous/folded blade cut; net passage area unavailable.")
    return float(min(theta)), float(max(theta))


def _wall_cut_radius(section, wall, hit, expected, tangent):
    """Use exact Hub/Tip limits within the two polyline sagitta budgets.

    The engine samples the exact wall, then samples the camber from that
    polyline. Two chord approximations can place its normal-line hit slightly
    inside the analytic wall. This is not a physically displaced end section.
    A displacement beyond the derived budget remains an error.
    """
    zr = np.column_stack((section.camber.z, section.camber.r))
    steps = np.diff(zr, axis=0)
    lengths = np.linalg.norm(steps, axis=1)
    index = np.argmin(np.linalg.norm((zr[:-1]+zr[1:])/2-hit[:2], axis=1))
    cosine = abs(float(steps[index] @ tangent))/max(float(lengths[index]), 1e-300)
    radii = [s.radius for s in wall.segments if hasattr(s, 'radius')]
    tolerance = 1e-7
    if radii:
        wall_step = float(np.max(np.hypot(np.diff(wall.z), np.diff(wall.r))))
        # Sum the wall-sampling and camber-sampling circular sagitta bounds.
        radius = min(radii)
        for chord in (wall_step, float(max(lengths))):
            if chord >= 2*radius:
                raise ValueError('Wall sampling too coarse for a reliable boundary cut.')
            sagitta = (chord/2)**2/(radius+np.sqrt(radius**2-(chord/2)**2))
            tolerance += sagitta/max(cosine, 1e-12)
    if np.linalg.norm(hit[:2]-expected) > tolerance:
        raise ValueError('Hub/Tip cut is displaced beyond wall-sampling error.')
    return float(expected[1])


def _area_cut(row, station, pitch, sign):
    # A normal to a folded return path can also cross a remote upstream blade.
    # Keep only stations whose Hub foot lies on this row's physical LE–TE run.
    # Do not mistake the remote intersection for a displaced Hub section.
    distances=row.sections[0].camber.meridional_distance
    if distances is not None:
        from .blade_edge import project_to_wall
        fraction,_=project_to_wall(row.hub,[station.hub_z,station.hub_r])
        distance=fraction*row.hub.length;tolerance=row.hub.length*1e-6
        if distance<distances[0]-tolerance or distance>distances[-1]+tolerance:
            return None
    h = np.array([station.hub_z, station.hub_r])
    s = np.array([station.shroud_z, station.shroud_r])
    length = np.linalg.norm(s-h)
    normal = (s-h)/length
    tangent = np.array([normal[1], -normal[0]])
    mean = np.array([station.z_mean, station.r_mean])
    blocked, split_blocked, gaps1, gaps2, positions, radii = [], [], [], [], [], []
    split_present = []
    for index, section in enumerate(row.sections):
        camber = _hits(section.camber, mean, tangent)
        if not len(camber):
            return None  # Not within the LE/TE overlap of every span.
        if len(camber) != 1:
            raise ValueError("Ambiguous camber cross-flow cut.")
        z, r, _ = camber[0]
        position = float((np.array([z, r])-h) @ normal)
        if index == 0:
            r = _wall_cut_radius(section, row.hub, camber[0], h, tangent)
            position = 0.
        elif index == len(row.sections)-1:
            if row.tip is None:
                r = _wall_cut_radius(section, row.shroud, camber[0], s, tangent)
                position = length
        positions.append(position)
        radii.append(r)
        interval = _interval(section, mean, tangent, sign)
        if interval is None:
            raise ValueError("Missing main blade cut.")
        lo, hi = interval
        if hi-lo >= pitch:
            raise ValueError("Main blade blocks/overlaps adjacent pitch.")
        blocked.append((hi-lo)*r)
        split = None if not row.splitter_sections else _interval(row.splitter_sections[index], mean, tangent, sign)
        split_present.append(split is not None)
        if split is None:
            split_blocked.append(0.)
        else:
            sl, sh = split
            # Keep the splitter in this passage while allowing arbitrary wrap.
            shift = np.floor(((lo+hi)/2-(sl+sh)/2)/pitch)+1
            sl, sh = sl+shift*pitch, sh+shift*pitch
            if sl < hi-1e-9 or sh > lo+pitch+1e-9:
                raise ValueError("Splitter overlaps main blade or adjacent pitch.")
            split_blocked.append((sh-sl)*r)
            gaps1.append((sl-hi)*r)
            gaps2.append((lo+pitch-sh)*r)
    positions = np.asarray(positions)
    if (abs(positions[0]) > 1e-5 or positions[-1]>length+1e-5 or positions[-1]<=0
            or np.any(np.diff(positions) <= 0)):
        raise ValueError("Span cuts do not cover Hub–Shroud monotonically.")
    integrate = lambda values: float(np.sum((np.asarray(values)[1:]+np.asarray(values)[:-1])/2*np.diff(positions)))
    reference = station.gross_area*pitch/(2*np.pi)-integrate(blocked)
    net = reference-integrate(split_blocked)
    bypass=0. if row.tip is None else station.gross_area*pitch/(2*np.pi)-pitch*integrate(radii)
    if bypass < -1e-5:
        raise ValueError('Tip clearance cut extends outside the casing.')
    bypass=max(0.,bypass)
    if net <= 0:
        raise ValueError("Non-positive net passage area.")
    return PassageAreaStation(station.m_flow_norm, station.gross_area, reference, net,
                              integrate(gaps1) if all(split_present) else None,
                              integrate(gaps2) if all(split_present) else None,bypass)


def calculate_passages(row, vane_count, rotation_sign=1, *, points=101, mean_points=4001):
    """Measure one row; main–main is only a reference when a splitter exists."""
    if isinstance(vane_count, bool) or not isinstance(vane_count, int) or vane_count < 2:
        raise ValueError("Passage measurements require at least two main blades.")
    if isinstance(rotation_sign, bool) or rotation_sign not in (-1, 1):
        raise ValueError("Rotation sign must be +1 or -1.")
    spans = np.array([s.span for s in row.sections])
    if len(spans) < 2 or not np.isfinite(spans).all() or spans[0] != 0 or spans[-1] != 1 or np.any(np.diff(spans) <= 0):
        raise ValueError("Ordered Hub–Tip sections are required.")
    if row.splitter_sections and [s.span for s in row.splitter_sections] != list(spans):
        raise ValueError("Splitter spans must match main blade spans.")
    result = PassageResult(vane_count)
    pitch = 2*np.pi/vane_count
    cuts = calculate_flow_area(row.hub, row.shroud, points=points, mean_points=mean_points, strict=False)
    result.errors.extend(cuts.errors)
    for station in cuts.stations:
        try:
            area = _area_cut(row, station, pitch, rotation_sign)
            if area is not None:
                result.stations.append(area)
        except ValueError as exc:
            result.errors.append(f"m={station.m_flow_norm:.6g}: {exc}")
    if not result.stations:
        result.errors.append("No cross-flow station spans all main sections; extend walls or refine sampling.")
    pairs = [('Main–Main', row.sections, row.sections, rotation_sign*pitch, bool(row.splitter_sections))]
    if row.splitter_sections:
        pairs.extend([('Main–Splitter', row.sections, row.splitter_sections, 0., False),
                      ('Splitter–Main', row.splitter_sections, row.sections, rotation_sign*pitch, False)])
    for name, first, second, angle, reference in pairs:
        if any('overlap' in error or 'blocks/' in error for error in result.errors):
            result.errors.append(f"{name}: invalid overlapping passage; throat unavailable.")
            continue
        try:
            result.throats.append(_throat(name, first, second, angle, reference))
        except ValueError as exc:
            result.errors.append(str(exc))
    return result
