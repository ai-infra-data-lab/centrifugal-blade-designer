"""Cylinder intersections in a sampled meridional chart, independent of Qt."""
import numpy as np
from scipy.integrate import quad


def cylinder_distance(wall_m, wall_zr, radius, reference_m):
    """Choose the cylinder intersection nearest the requested TE station."""
    candidates = []
    for i, (r0, r1) in enumerate(zip(wall_zr[:-1, 1], wall_zr[1:, 1])):
        if abs(r1-r0) < 1e-12:
            if abs(r0-radius) < 1e-9:
                candidates.append(float(np.clip(reference_m, wall_m[i], wall_m[i+1])))
        elif min(r0, r1)-1e-10 <= radius <= max(r0, r1)+1e-10:
            fraction = np.clip((radius-r0)/(r1-r0), 0., 1.)
            candidates.append(float(wall_m[i]+fraction*(wall_m[i+1]-wall_m[i])))
    if not candidates:
        raise ValueError("TE Cutoff: span wall does not reach the Hub TE cylinder radius.")
    return min(candidates, key=lambda distance: abs(distance-reference_m))


def cut_surface(distance, theta, tangential, normalized, cut_m,
                end_offset, end_beta, wall_m, wall_r, rotation_sign, blade_length):
    """Trim the long side; extend the short side with terminal beta/thickness.

    Coordinates are intrinsic (meridional distance, camber angle, tangential
    offset). Extension only determines the camber angle of the cut endpoint;
    the physical surface remains on the finite wall at cut_m.
    """
    hits = np.flatnonzero(distance >= cut_m)
    if len(hits):
        i = int(hits[0])
        if i == 0:
            raise ValueError("TE Cutoff cylinder intersects the blade leading edge.")
        fraction = (cut_m-distance[i-1])/(distance[i]-distance[i-1])
        values = [a[i-1]+fraction*(a[i]-a[i-1]) for a in (theta, tangential, normalized)]
        return (np.r_[distance[:i], cut_m],
                *(np.r_[a[:i], value] for a, value in zip((theta, tangential, normalized), values)))
    virtual_end = cut_m-end_offset
    # Continue the terminal wall tangent if the virtual camber lies beyond the
    # finite flow path. No physical profile point is placed outside that path.
    slope = (wall_r[-1]-wall_r[-2])/(wall_m[-1]-wall_m[-2])
    def inverse_radius(m):
        r = (wall_r[-1]+slope*(m-wall_m[-1]) if m > wall_m[-1]
             else np.interp(m, wall_m, wall_r))
        if r <= 0:
            raise ValueError("TE Cutoff extension requires positive radius.")
        return 1./r
    knots = wall_m[(wall_m > cut_m) & (wall_m < virtual_end)]
    integral = quad(inverse_radius, cut_m, virtual_end, points=knots,
                    limit=max(50,len(knots)+2))[0]
    end_theta = theta[-1]+rotation_sign*np.tan(end_beta)*integral
    return (np.r_[distance, cut_m], np.r_[theta, end_theta],
            np.r_[tangential, tangential[-1]],
            np.r_[normalized, 1.+(virtual_end-cut_m)/blade_length])
