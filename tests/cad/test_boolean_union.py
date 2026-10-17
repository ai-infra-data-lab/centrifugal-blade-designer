def test_single_and_periodic_are_connected(native_assembly):
    r=native_assembly['report'];assert r['boolean_status']=='PASS'
    assert r['checks']['result']['solid_count']==1
    assert r['checks']['result']['closed_shell']
