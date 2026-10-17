from blade_designer.cad.client import publish_job
from blade_designer.fileio.turbogrid_export import export_turbogrid

def test_profile_points_unchanged_and_cad_requires_conversion(native_assembly,tmp_path):
    p=native_assembly['params'];original=export_turbogrid(tmp_path/'original',p)
    r=publish_job(native_assembly['job'],tmp_path/'case',p)
    assert r['artifacts']['turbogrid_profile_points']['status']=='PASS'
    for path in original:assert path.read_bytes()==(tmp_path/'case'/'turbogrid'/'profile_points'/path.name).read_bytes()
    assert r['artifacts']['turbogrid_cad']['status']=='CONVERSION_REQUIRED'
    assert r['turbogrid_import']==r['turbogrid_mesh']=='NOT_TESTED'
    assert r['parasolid']=='UNAVAILABLE' and r['overall']!='PASS'
