from copy import deepcopy
import numpy as np
import pytest
from blade_designer.cad.reference_report import adopted_surface_counts
from blade_designer.geometry.cad_surface_reference import reference_surfaces
from blade_designer.geometry.geometry_3d import generate_impeller
from test_cylindrical_cutoff import radial_parameters

HASH='a'*64


def cad_report(digest=HASH):
    counts={'le':33,'ps':65,'te':129,'ss':257}
    metrics={'brep_valid':True,'self_intersection_free':True,'closed_shell':True,'solid_count':1,'surface_grid_counts':counts}
    return {'parameter_snapshot_hash':digest,'geometry_type':'impeller','cad_unit':'mm','rotation_axis':'Z',
        'overall':'WARNING','cad_surface_status':'PASS','blade_solid_status':'PASS',
        'checks':{'blade_solids':{'main':metrics,'splitter':{**deepcopy(metrics),'surface_grid_counts':{'le':513,'ps':129,'te':65,'ss':33}}}}}


@pytest.mark.parametrize('group',['main','splitter'])
def test_selected_counts_are_copied_and_each_role_uses_its_own_density(group):
    report=cad_report();before=deepcopy(report)
    counts=adopted_surface_counts(report,HASH,group)
    p=radial_parameters();g=generate_impeller(p)
    combined=reference_surfaces(g.sections,p.sections,counts)
    for role,n in counts.items():
        scalar=reference_surfaces(g.sections,p.sections,n)[role]
        np.testing.assert_array_equal(combined[role].across.c,scalar.across.c)
        np.testing.assert_array_equal(combined[role].along.t,scalar.along.t)
    counts['le']=65
    assert report==before


@pytest.mark.parametrize('bad',['none','snapshot','hash','kind','unit','axis','failed','surface','solid',
    'checks','missing_group','closed','brep','interference','solid_count','roles','extra_role','bool','float','density'])
def test_incomplete_stale_failed_or_invalid_report_is_not_a_fallback(bad):
    report=cad_report();digest=HASH
    if bad=='none':report=None
    elif bad=='snapshot':report['parameter_snapshot_hash']='b'*64
    elif bad=='hash':digest='not-a-digest'
    elif bad=='kind':report['geometry_type']='diffuser'
    elif bad=='unit':report['cad_unit']='m'
    elif bad=='axis':report['rotation_axis']='X'
    elif bad=='failed':report['overall']='FAIL'
    elif bad=='surface':report['cad_surface_status']='NOT_TESTED'
    elif bad=='solid':report['blade_solid_status']='FAIL'
    elif bad=='checks':report['checks']=None
    elif bad=='missing_group':del report['checks']['blade_solids']['main']
    else:
        m=report['checks']['blade_solids']['main']
        if bad=='closed':m['closed_shell']=False
        elif bad=='brep':m['brep_valid']=False
        elif bad=='interference':m['self_intersection_free']=False
        elif bad=='solid_count':m['solid_count']=True
        elif bad=='roles':del m['surface_grid_counts']['ss']
        elif bad=='extra_role':m['surface_grid_counts']['camber']=65
        elif bad=='bool':m['surface_grid_counts']['ps']=True
        elif bad=='float':m['surface_grid_counts']['ps']=65.
        elif bad=='density':m['surface_grid_counts']['ps']=66
    before=deepcopy(report)
    with pytest.raises(ValueError):adopted_surface_counts(report,digest,'main')
    assert report==before


@pytest.mark.parametrize('counts',[{'ps':65},{'le':33,'ps':65,'te':129,'ss':257,'cap':33}])
def test_numeric_reference_requires_complete_role_map(counts):
    p=radial_parameters();g=generate_impeller(p)
    with pytest.raises(ValueError,match='four'):reference_surfaces(g.sections,p.sections,counts)
