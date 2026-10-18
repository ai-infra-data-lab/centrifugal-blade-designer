"""Nonlocal self/nearest-periodic contact screening of explicit sampled grids.

No geometry regeneration, CAD imports, Qt, export gate or hidden mesh density.
Caller supplies the source surface samples in mm and the main-blade count.
"""
from collections.abc import Mapping
import numpy as np
from .annulus import rotate_xy
from .mesh_contacts import grid_mesh, mesh_contacts, _positive_int, _nonnegative


ROLES=('le','ps','te','ss')


def _meshes(grids, max_triangles):
    if not isinstance(grids,Mapping) or set(grids)!=set(ROLES):
        raise ValueError('All four LE/PS/TE/SS surface grids must be supplied.')
    result={}
    for role in ROLES:
        grid=np.asarray(grids[role])
        if grid.ndim==3 and 2*(grid.shape[0]-1)*(grid.shape[1]-1)>max_triangles:
            raise ValueError('Surface grid exceeds max_triangles_per_patch.')
        result[role]=grid_mesh(grid)
    return result


def screen_blade_grids(main, blade_count, *, splitter=None, tolerance_mm,
                       area_epsilon_mm2, max_work_per_pair=500000,
                       max_contacts_per_pair=100, max_triangles_per_patch=20000):
    """Screen explicit triangle approximations; NO_CONTACT_OBSERVED is not PASS.

    Tests self faces within each role, main-main and splitter-splitter at +1
    pitch, and main-splitter at offsets 0/-1/+1 (deduplicated modulo count).
    Within-role shared-vertex neighbors, cross-role self contacts, other pitch
    offsets, solid containment, caps/walls/fillets remain explicitly untested.
    One splitter per main pitch is assumed; its phase is already in its grid.
    Per-pair resource/degeneracy failures propagate to aggregate completeness.
    """
    _positive_int(blade_count,'blade_count')
    _nonnegative(tolerance_mm,'tolerance_mm');_nonnegative(area_epsilon_mm2,'area_epsilon_mm2')
    for value,name in ((max_work_per_pair,'max_work_per_pair'),(max_contacts_per_pair,'max_contacts_per_pair'),
                       (max_triangles_per_patch,'max_triangles_per_patch')):_positive_int(value,name)
    sources={'Main':main}
    if splitter is not None:sources['Splitter']=splitter
    groups={name:_meshes(grids,max_triangles_per_patch) for name,grids in sources.items()}
    checks=[]

    def check(group_a,role_a,group_b=None,role_b=None,offset=0):
        va,fa=groups[group_a][role_a]
        kwargs={}
        if group_b is not None:
            vb,fb=groups[group_b][role_b]
            x,y=rotate_xy(vb[:,0],vb[:,1],2*np.pi*offset/blade_count)
            kwargs={'second_vertices':np.column_stack((x,y,vb[:,2])),'second_faces':fb}
        report=mesh_contacts(va,fa,**kwargs,tolerance_mm=tolerance_mm,area_epsilon_mm2=area_epsilon_mm2,
                             max_work=max_work_per_pair,max_contacts=max_contacts_per_pair,
                             max_triangles=max_triangles_per_patch)
        checks.append({'first_group':group_a,'first_role':role_a,'second_group':group_b,
                       'second_role':role_b,'pitch_offset':offset,'report':report})

    for group in groups:
        for role in ROLES:check(group,role)
        if blade_count>1:
            for a in ROLES:
                for b in ROLES:check(group,a,group,b,1)
    offsets=[]
    if splitter is not None:
        for offset in (0,-1,1):
            if offset%blade_count not in [v%blade_count for v in offsets]:offsets.append(offset)
        for offset in offsets:
            for a in ROLES:
                for b in ROLES:check('Main',a,'Splitter',b,offset)
    found=sum(c['report']['contact_count'] for c in checks)
    complete=all(c['report']['scan_complete'] for c in checks)
    return {'status':'CONTACT_CANDIDATES_FOUND' if found else 'NO_CONTACT_OBSERVED' if complete else 'INCOMPLETE',
            'checks':checks,'check_count':len(checks),'contact_count':found,'scan_complete':complete,
            'incomplete_checks':sum(not c['report']['scan_complete'] for c in checks),
            'blade_count':blade_count,'splitter_pitch_offsets':offsets,
            'source_model':'caller_supplied_XYZ_grids','axis':'Z','units':'mm',
            'grid_shapes':{name:{role:list(np.asarray(grids[role]).shape) for role in ROLES}
                           for name,grids in sources.items()},
            'unchecked':['shared-vertex local neighbors within a role','cross-role self contacts',
                         'non-neighbor periodic offsets','solid containment',
                         'Hub/Tip caps, walls, disk and fillets','continuous surface between sample points'],
            'continuous_surface_certified':False,'roundoff_certified':False,'whole_geometry_verified':False}
