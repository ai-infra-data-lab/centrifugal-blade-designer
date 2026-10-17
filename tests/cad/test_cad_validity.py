def test_full_impeller_interference_and_validity(native_assembly):
    r=native_assembly['report'];assert r['checks']['inter_blade_interference']=='PASS'
    assert r['checks']['max_overlap_volume_mm3']<=1e-6
    m=r['checks']['full_impeller'];assert m['solid_count']==1 and m['self_intersection_free']
    assert m['volume_mm3']>r['checks']['single_assembly']['volume_mm3']
