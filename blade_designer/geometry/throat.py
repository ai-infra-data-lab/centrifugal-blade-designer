"""Continuous closest distance on every master-segment spline pair."""
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from ..models.geometry import BladeSegment, BladeSurfaceGeometry, ThroatResult
from .resample import arc_length, segment_spline
from .pitch import angular_pitch


def closest_on_segments(first: BladeSegment, second: BladeSegment) -> tuple[float, np.ndarray, np.ndarray, float, float]:
    sa, ca = segment_spline(first)
    sb, cb = segment_spline(second)
    la, lb = float(sa[-1]), float(sb[-1])
    def evaluate(curve: object, point: np.ndarray, length: float, t: float) -> np.ndarray:
        return point if curve is None else curve(t * length)
    def point_a(t: float) -> np.ndarray:
        return evaluate(ca, first.xy[0], la, t)
    def point_b(t: float) -> np.ndarray:
        return evaluate(cb, second.xy[0], lb, t)
    def objective(t: np.ndarray) -> tuple[float, np.ndarray]:
        delta = point_a(t[0]) - point_b(t[1])
        da = np.zeros(2) if ca is None else ca(t[0]*la, 1)*la
        db = np.zeros(2) if cb is None else cb(t[1]*lb, 1)*lb
        return float(delta @ delta), 2*np.array([delta @ da, -delta @ db])
    distances, nearest = cKDTree(second.xy).query(first.xy)
    # All coarse local minima plus the best sample and boundary starts.
    local = np.flatnonzero((distances <= np.r_[np.inf, distances[:-1]]) &
                           (distances <= np.r_[distances[1:], np.inf]))
    local = local[np.argsort(distances[local])[:16]]
    af, bf = arc_length(first), arc_length(second)
    seeds = [(float(af[i]/la) if la else 0., float(bf[nearest[i]]/lb) if lb else 0.) for i in local]
    seeds += [(0., 0.), (0., 1.), (1., 0.), (1., 1.)]
    best = (float("inf"), np.zeros(2))
    for seed in seeds:
        result = minimize(objective, seed, jac=True, method="L-BFGS-B", bounds=((0., 1.), (0., 1.)),
                          options={"ftol": 1e-14, "gtol": 1e-10, "maxiter": 150})
        for candidate in (np.array(seed), result.x):
            value = objective(candidate)[0]
            if value < best[0]:
                best = (value, candidate)
    t = best[1]
    return float(np.sqrt(max(best[0], 0.))), point_a(t[0]), point_b(t[1]), float(t[0]), float(t[1])


def calculate_throat(surfaces: BladeSurfaceGeometry, vane_count: int) -> ThroatResult | None:
    if vane_count == 1:
        return None  # There is no distinct adjacent blade.
    angle = angular_pitch(vane_count)
    c, s = np.cos(angle), np.sin(angle)
    rotated = {}
    names = ("PS", "SS", "LE", "TE")
    for name in names:
        segment = getattr(surfaces, name.lower())
        rotated[name] = BladeSegment(c*segment.x - s*segment.y, s*segment.x + c*segment.y, segment.m_norm)
    best = None
    for name1 in names:
        first = getattr(surfaces, name1.lower())
        for name2 in names:
            second = rotated[name2]
            width, a, b, t1, t2 = closest_on_segments(first, second)
            if best is None or width < best.width - 1e-10:
                def m_at(segment: BladeSegment, t: float) -> float | None:
                    if segment.m_norm is None:
                        return None
                    lengths = arc_length(segment)
                    return float(np.interp(t*lengths[-1], lengths, segment.m_norm))
                best = ThroatResult(width, float(a[0]), float(a[1]), float(b[0]), float(b[1]),
                                    name1, name2, m_at(first, t1), m_at(second, t2))
    return best
