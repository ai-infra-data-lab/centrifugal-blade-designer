"""Beta-preserving impeller stacking. No Qt, file formats or optimization UI.

Rake is the signed angle of the Hub-to-Tip TE camber chord out of the
meridional plane through its midpoint. Positive means increasing theta (+Z CCW).
The Hub section stays fixed; intermediate TE theta values interpolate by span.
"""
from copy import deepcopy
import numpy as np
from scipy.optimize import brentq, minimize_scalar
from ..models.validation import is_finite_number


def _chord_rake(r_hub,r_tip,dz,delta):
    # Place Hub at theta=0. The midpoint selects the reference meridional plane.
    hub=np.array([r_hub,0.,0.])
    tip=np.array([r_tip*np.cos(delta),r_tip*np.sin(delta),dz])
    midpoint=(hub+tip)/2
    radius=np.hypot(*midpoint[:2])
    if radius<1e-12:raise ValueError("TE Rake reference plane lies on the rotation axis.")
    normal=np.array([-midpoint[1],midpoint[0],0.])/radius
    chord=tip-hub
    tangential=float(chord@normal)
    meridional=np.linalg.norm(chord-tangential*normal)
    return float(np.arctan2(tangential,meridional))


def measure_te_rake(geometry):
    hub,tip=(geometry.sections[i].camber for i in (0,-1))
    delta=float(tip.theta_rad[-1]-hub.theta_rad[-1])
    return float(np.rad2deg(_chord_rake(hub.r[-1],tip.r[-1],tip.z[-1]-hub.z[-1],delta)))


class ImpellerParameterMapper:
    @staticmethod
    def map_te_rake(geometry,target_deg):
        if not is_finite_number(target_deg) or not -90<target_deg<90:
            raise ValueError("TE Rake must be finite and strictly between -90 and 90 degrees.")
        hub,tip=(geometry.sections[i].camber for i in (0,-1))
        rh,rt,dz=float(hub.r[-1]),float(tip.r[-1]),float(tip.z[-1]-hub.z[-1])
        if np.hypot(rt-rh,dz)<1e-9:
            raise ValueError("TE Rake requires distinct Hub and Tip meridional endpoints.")
        target=abs(np.deg2rad(float(target_deg)))
        if target==0:delta=0.
        else:
            # Use the first (smallest twist) solution, before the maximum rake.
            limit=np.pi-1e-7
            peak=minimize_scalar(lambda angle:-_chord_rake(rh,rt,dz,angle),
                                 bounds=(0.,limit),method='bounded',options={'xatol':1e-12})
            maximum=_chord_rake(rh,rt,dz,peak.x)
            if not peak.success or target>maximum+1e-12:
                raise ValueError("TE Rake target is unreachable with the fixed meridional endpoints and TE radii.")
            delta=brentq(lambda angle:_chord_rake(rh,rt,dz,angle)-target,
                         0.,peak.x,xtol=1e-13) if target<maximum else float(peak.x)
            delta=np.copysign(delta,target_deg)
        result=deepcopy(geometry)
        anchor=float(hub.theta_rad[-1])
        for section in result.sections[1:]:
            # theta_LE = target theta_TE - integral(beta/r dm).
            # A rigid rotation of the already integrated section is equivalent.
            target_te=anchor+section.span*delta
            offset=target_te-float(section.camber.theta_rad[-1])
            seen=set()
            for name in ('camber','le','ps','te','ss','master_le','master_ps','master_te','master_ss'):
                curve=getattr(section,name)
                if id(curve.theta_rad) not in seen:
                    seen.add(id(curve.theta_rad));curve.theta_rad+=offset
        if not np.isclose(measure_te_rake(result),target_deg,rtol=0,atol=1e-7):
            raise ValueError("TE Rake mapping did not reach the target.")
        return result
