from blade_designer.cad.client import publish_job

def test_impossible_r8_never_reduced_and_preserves_existing_step(native_failure,tmp_path):
    r=native_failure['report'];assert r['overall']=='FAIL'
    assert native_failure['params'].cad_export.fillet.hub_radius_mm==8
    assert not r['artifacts'].get('mechanical',{}).get('files')
    case=tmp_path/'case';folder=case/'mechanical';folder.mkdir(parents=True)
    good=folder/'impeller_blade_hub_R8.step';good.write_bytes(b'existing valid model sentinel')
    publish_job(native_failure['job'],case,native_failure['params'])
    assert good.read_bytes()==b'existing valid model sentinel'
    assert not (case/'validation'/'cad_validation.json').exists()
