def test_blade_only_is_one_nonzero_closed_solid_and_not_r8(native_blade):
    r=native_blade['report'];assert r['solid_validity']=='PASS'
    m=r['checks']['result'];assert m['solid_count']==1 and m['volume_mm3']>0 and m['self_intersection_free']
    assert r['fillet_status']=='NOT_APPLICABLE'
    assert r['checks']['blade_solids']['main']['cap_methods']==['plane','plane']
    assert r['checks']['inter_blade_interference'].startswith('NOT_TESTED')
    assert all('NO_FILLET' in name for name in r['artifacts']['mechanical']['files'])
