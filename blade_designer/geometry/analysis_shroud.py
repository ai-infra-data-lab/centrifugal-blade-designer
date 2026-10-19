"""A second casing about an unchanged physical Tip; no Qt or file formats.

Both clearances use the drawing casing's inward normals. The new casing is
Tip minus analysis gap times that normal. It does not regenerate any blade.
"""
from dataclasses import replace
import numpy as np
from ..models.geometry_3d import AnalysisShroudGeometry, TipMeridionalGeometry
from .tip_clearance import _frame, _check_open_curve
from .impeller_trim import _wall, _Boundary
from .meridional_segments import sample_meridional, validate_flow_path
from .blade_edge import project_to_wall


def make_analysis_shroud(params, geometry):
    settings=params.tip_clearance
    if settings is None or (settings.analysis_le_mm,settings.analysis_te_mm)==(None,None):
        return None
    values=(settings.analysis_le_mm,settings.analysis_te_mm)
    from ..models.validation import is_finite_number
    if any(not is_finite_number(v) or v<0 for v in values):
        raise ValueError('Analysis clearance requires finite LE and TE values >= 0 mm.')
    wall=geometry.shroud
    tip=geometry.tip
    # Use the actual retained endpoints, including an outer-diameter trim.
    camber=geometry.sections[-1].camber
    def distance(point):
        if not hasattr(wall,'source_m'):return project_to_wall(wall,point)[0]*wall.length
        points=np.column_stack((wall.z,wall.r));delta=np.diff(points,axis=0)
        fractions=np.clip(np.einsum('ij,ij->i',point-points[:-1],delta)/np.einsum('ij,ij->i',delta,delta),0,1)
        nearest=points[:-1]+fractions[:,None]*delta
        index=int(np.argmin(np.linalg.norm(nearest-point,axis=1)))
        return float(wall.m[index]+fractions[index]*(wall.m[index+1]-wall.m[index]))
    le,te=[distance(np.array([camber.z[i],camber.r[i]])) for i in (0,-1)]
    if te<=le+1e-9:
        raise ValueError('Analysis Shroud: TE must follow LE on the drawing casing.')
    source=np.asarray(tip.casing_m if tip is not None else wall.m)
    distances=np.unique(np.r_[source,le,te])
    # Analytic projection can reproduce an existing node a few ULPs away.
    # Remove only roundoff duplicate parameters, not short geometric segments.
    roundoff=64*np.finfo(float).eps*max(1.,wall.length)
    distances=distances[np.r_[True,np.diff(distances)>roundoff]]
    casing,normals,_=_frame(geometry.hub,wall,distances)
    if hasattr(wall,'source_m'):
        # Trim's casing is a polyline. Its drawing Tip uses vertex normals,
        # rather than discontinuous individual segment normals at every join.
        vertex=_Boundary(np.column_stack((wall.z,wall.r)),geometry.hub).normals
        normals=np.column_stack([np.interp(distances,wall.m,vertex[:,i]) for i in (0,1)])
        normals/=np.linalg.norm(normals,axis=1)[:,None]
    physical=(np.column_stack([np.interp(distances,source,v) for v in (tip.z,tip.r)])
              if tip is not None else casing.copy())
    gap=np.interp(distances,[le,te],values)
    points=physical-gap[:,None]*normals
    if not np.isfinite(points).all() or np.any(points[:,1]<=0):
        raise ValueError('Analysis Shroud requires finite positive radii.')
    if np.any(np.einsum('ij,ij->i',np.diff(points,axis=0),np.diff(casing,axis=0))<=0):
        raise ValueError('Analysis Shroud folds or reverses along the drawing casing.')
    _check_open_curve(points)
    # Validate the side and available passage width at the same correspondence.
    hub=sample_meridional(geometry.hub,distances/wall.length*geometry.hub.length)
    if np.any(np.einsum('ij,ij->i',points-hub,normals)>=-1e-8):
        raise ValueError('Analysis Shroud reaches or crosses the Hub.')
    boundaries=(wall.source_boundaries if hasattr(wall,'source_boundaries') else
                np.r_[0.,np.cumsum([s.length for s in wall.segments])])
    original=np.interp(distances,wall.m,wall.source_m) if hasattr(wall,'source_m') else distances
    result=_wall(points,original,boundaries)
    validate_flow_path(geometry.hub,result)
    return AnalysisShroudGeometry(result,distances,physical[:,0],physical[:,1],gap,float(le),float(te))


def analysis_export_geometry(geometry):
    """Select the analysis casing while retaining every physical blade point."""
    data=geometry.analysis_shroud
    if data is None:return geometry
    wall=data.wall
    tip=None
    if np.any(data.clearance_mm>0):
        le,te=np.interp([data.le_drawing_m,data.te_drawing_m],data.drawing_m,wall.m)
        tip=TipMeridionalGeometry(wall.m,data.tip_z,data.tip_r,data.clearance_mm,float(le),float(te))
    return replace(geometry,shroud=wall,tip=tip)
