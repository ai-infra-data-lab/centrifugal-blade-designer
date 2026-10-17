from blade_designer.cad.client import publish_job

def test_mechanical_r8_published_independently_of_conversion(native_assembly,tmp_path):
    r=publish_job(native_assembly['job'],tmp_path/'case',native_assembly['params'])
    assert r['artifacts']['mechanical']['status']=='PASS',r.get('error')
    assert r['mechanical_import']=='NOT_TESTED' and r['mechanical_mesh']=='NOT_TESTED'
    for name in r['artifacts']['mechanical']['files']:assert (tmp_path/'case'/name).is_file()
