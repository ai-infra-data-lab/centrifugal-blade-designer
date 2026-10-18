"""Shared CAD tangent law and numerical reference, without Qt or a CAD kernel."""
import numpy as np
from collections.abc import Mapping
from scipy.interpolate import make_interp_spline
from .surface_correspondence import cad_curve_coordinates
from .surface_evaluation import fit_surface_spline


def join_surface_tangents(sections):
    # Preserve the CAD endpoint construction, order and cutoff exceptions.
    values={}
    for role in ("le","ps","te","ss"):
        endpoints=[]
        for section in sections:
            row=np.asarray(section[role]);xi=np.asarray(section.get(role+"_xi",np.linspace(0,1,len(row))))
            spline=make_interp_spline(xi,row,k=min(3,len(row)-1))
            endpoints.append([spline.derivative()(0.),spline.derivative()(1.)])
        values[role]=np.asarray(endpoints)
    for a,ia,b,ib,sign,edge_role in (("le",1,"ps",0,1,"le"),("ps",1,"te",0,1,"te"),("te",1,"ss",1,-1,"te"),("ss",0,"le",0,-1,"le")):
        if any(section.get(edge_role+"_type","circular")=="cutoff" for section in sections):continue
        va=values[a][:,ia].copy();vb=values[b][:,ib].copy()*sign
        ma=np.linalg.norm(va,axis=1);mb=np.linalg.norm(vb,axis=1)
        direction=va/ma[:,None]+vb/mb[:,None];direction/=np.linalg.norm(direction,axis=1)[:,None]
        values[a][:,ia]=direction*float(np.median(ma))
        values[b][:,ib]=sign*direction*float(np.median(mb))
    return {name:(array[:,0],array[:,1]) for name,array in values.items()}


def reference_surfaces(sections, profiles, density):
    """Same master xi and edge types as CAD jobs; explicit fixed fit density.

    This does not perform CAD's adaptive master-point acceptance, cap/sewing,
    solid validation or export. Callers must reject unsupported trimmed inputs.
    """
    if len(sections) != len(profiles):raise ValueError('Profile/geometry section count mismatch.')
    if isinstance(density,Mapping) and set(density)!=set(('le','ps','te','ss')):
        raise ValueError('Reference densities must specify all four contour roles.')
    payload=[]
    for section,profile in zip(sections,profiles):
        entry={'span':section.span, 'le_type':profile.edge_parameters.le_type.value,
               'te_type':profile.edge_parameters.te_type.value}
        for role in ('le','ps','te','ss'):
            curve=getattr(section,'master_'+role)
            entry[role]=curve.xyz;entry[role+'_xi']=cad_curve_coordinates(curve)
        payload.append(entry)
    tangents=join_surface_tangents(payload)
    return {role:fit_surface_spline([s[role] for s in payload],density[role] if isinstance(density,Mapping) else density,
            [s[role+'_xi'] for s in payload],[s['span'] for s in payload],tangents[role])
            for role in ('le','ps','te','ss')}


def reference_lines(surfaces, section_spans):
    """Render samples of the actual fitted surfaces; no chord interpolation."""
    lines={};spans=np.linspace(0,1,31);xi=np.linspace(0,1,101)
    colors={'le':'#e5c76b','ps':'#56d9e0','te':'#eead72','ss':'#f6948c'}
    for role,surface in surfaces.items():
        grid=surface.evaluate_grid(spans,xi)
        for i in range(0,len(xi),5):lines[f'Spanwise {role.upper()} {i}']=(grid[:,i], '#496b8e')
        for span,row in zip(section_spans,surface.evaluate_grid(section_spans,xi)):
            label='Hub' if span==0 else 'Tip' if span==1 else f'Span {span:.6g}'
            lines[f'{label} {role}']=(row,colors[role])
    return lines
