"""Render-only quads for a wall revolved about Z; no Qt or export dependency."""
import numpy as np


def revolve_wall(wall, max_wall_points=49, angular_segments=48):
    for value, minimum in ((max_wall_points,2),(angular_segments,3)):
        if isinstance(value,bool) or not isinstance(value,int) or value < minimum:
            raise ValueError("Invalid revolved surface sampling count.")
    r,z=np.asarray(wall.r),np.asarray(wall.z)
    if r.ndim != 1 or r.shape != z.shape or len(r)<2 or not np.isfinite([r,z]).all() or np.any(r<0):
        raise ValueError("Revolved wall requires finite matching Z/R arrays and nonnegative radii.")
    indices=np.linspace(0,len(r)-1,min(len(r),max_wall_points),dtype=int)
    theta=np.linspace(0,2*np.pi,angular_segments+1)
    grid=np.stack((r[indices,None]*np.cos(theta),r[indices,None]*np.sin(theta),
                   np.broadcast_to(z[indices,None],(len(indices),len(theta)))),axis=-1)
    grid[:,-1]=grid[:,0]  # exact seam closure
    return np.stack((grid[:-1,:-1],grid[1:,:-1],grid[1:,1:],grid[:-1,1:]),axis=2).reshape(-1,4,3)
