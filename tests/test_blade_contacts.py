"""Real row and analytic grid screening with explicit unchecked scopes."""
from copy import deepcopy
import numpy as np
import pytest
from blade_designer.geometry.blade_contacts import screen_blade_grids, ROLES
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.cad_surface_reference import reference_surfaces
from blade_designer.models.parameters import BladeParameters


def planes(offset=0):
    return {r:np.array([[[20.,0.,offset+10*i],[21.,0.,offset+10*i]],
                       [[20.,1.,offset+10*i],[21.,1.,offset+10*i]]]) for i,r in enumerate(ROLES)}


def test_separated_splitter_surfaces_have_only_scoped_no_contact_evidence():
    main=planes();splitter=planes(100);before=deepcopy((main,splitter))
    r=screen_blade_grids(main,1,splitter=splitter,tolerance_mm=0,area_epsilon_mm2=0)
    assert r['status']=='NO_CONTACT_OBSERVED' and r['scan_complete']
    assert r['check_count']==24 and r['splitter_pitch_offsets']==[0]
    assert r['whole_geometry_verified'] is False and 'solid containment' in r['unchecked']
    for old,new in zip(before,(main,splitter)):
        for role in ROLES:np.testing.assert_array_equal(old[role],new[role])


@pytest.mark.parametrize('count,checks,offsets',[(1,24,1),(2,72,2),(3,88,3),(20,88,3)])
def test_nearest_pitch_offsets_are_deduplicated_and_all_roles_are_present(count,checks,offsets):
    r=screen_blade_grids(planes(),count,splitter=planes(100),tolerance_mm=0,area_epsilon_mm2=0)
    assert r['check_count']==checks and len(r['splitter_pitch_offsets'])==offsets
    assert len({i%count for i in r['splitter_pitch_offsets']})==offsets
    pairs=[(c['first_role'],c['second_role']) for c in r['checks']
           if c['first_group']=='Main' and c['second_group']=='Splitter' and c['pitch_offset']==0]
    assert set(pairs)=={(a,b) for a in ROLES for b in ROLES}


def test_coincident_main_splitter_are_reported_at_pitch_zero():
    r=screen_blade_grids(planes(),20,splitter=planes(),tolerance_mm=1e-12,area_epsilon_mm2=0)
    found=[c for c in r['checks'] if c['report']['contact_count']]
    assert found and all(c['first_group']=='Main' and c['second_group']=='Splitter' and c['pitch_offset']==0 for c in found)
    assert r['status']=='CONTACT_CANDIDATES_FOUND'


def test_real_1000_blade_row_exposes_adjacent_pitch_contact_without_changing_geometry():
    p=BladeParameters();p.geometry.vane_count=1000
    geometry=generate_impeller(p)
    surfaces=reference_surfaces(geometry.sections,p.sections,33)
    grids={role:s.evaluate_grid(np.linspace(0,1,5),np.linspace(0,1,33)) for role,s in surfaces.items()}
    before=deepcopy(grids)
    r=screen_blade_grids(grids,p.geometry.vane_count,tolerance_mm=1e-9,area_epsilon_mm2=1e-16,
                         max_contacts_per_pair=20)
    periodic=[c for c in r['checks'] if c['pitch_offset']==1 and c['report']['contact_count']]
    assert periodic and r['status']=='CONTACT_CANDIDATES_FOUND'
    assert all(c['first_group']==c['second_group']=='Main' for c in periodic)
    assert r['blade_count']==1000 and r['whole_geometry_verified'] is False
    for role in ROLES:np.testing.assert_array_equal(grids[role],before[role])


def test_analytic_ps_ss_crossing_is_detected_after_one_positive_z_pitch():
    grids=planes();count=8;angle=-2*np.pi/count
    # Main PS is the horizontal square at z=10. The adjacent SS is a
    # vertical rectangle crossing its interior; inverse-rotate its source.
    target=np.array([[[20.5,0.,9.],[20.5,1.,9.]],[[20.5,0.,11.],[20.5,1.,11.]]])
    xyz=target.copy();x,y=xyz[...,0].copy(),xyz[...,1].copy()
    xyz[...,0]=x*np.cos(angle)-y*np.sin(angle)
    xyz[...,1]=x*np.sin(angle)+y*np.cos(angle)
    grids['ss']=xyz
    result=screen_blade_grids(grids,count,tolerance_mm=1e-10,area_epsilon_mm2=0)
    pair=next(c for c in result['checks'] if c['first_role']=='ps' and c['second_role']=='ss' and c['pitch_offset']==1)
    assert pair['report']['contact_count']>0 and pair['report']['scan_complete']


def test_bad_mesh_and_resource_incompleteness_are_not_hidden_in_aggregate():
    degenerate=planes();degenerate['te'][:]=0
    r=screen_blade_grids(degenerate,1,tolerance_mm=0,area_epsilon_mm2=0)
    assert r['status']=='INCOMPLETE' and r['incomplete_checks']==1
    r=screen_blade_grids(planes(),1,tolerance_mm=0,area_epsilon_mm2=0,max_work_per_pair=1)
    assert r['status']=='INCOMPLETE' and r['incomplete_checks']==4


@pytest.mark.parametrize('options',[{'blade_count':0},{'blade_count':True},{'max_work_per_pair':0},
    {'max_triangles_per_patch':1},{'max_contacts_per_pair':False},{'tolerance_mm':-1}])
def test_invalid_row_or_resource_options_are_rejected(options):
    args={'blade_count':20,'tolerance_mm':0,'area_epsilon_mm2':0,**options}
    with pytest.raises(ValueError):screen_blade_grids(planes(),**args)


def test_missing_roles_are_not_replaced_or_ignored():
    main=planes();del main['ps']
    with pytest.raises(ValueError,match='four'):screen_blade_grids(main,20,tolerance_mm=0,area_epsilon_mm2=0)
