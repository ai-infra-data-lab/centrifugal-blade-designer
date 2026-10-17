def test_step_units_volume_and_bounds(native_assembly):
    a=native_assembly['report']['artifacts']['mechanical']['roundtrip']
    assert a['status']=='PASS' and a['units_mm']=='PASS'
    assert a['original']['solid_count']==a['imported']['solid_count']==1
    assert a['volume_difference_mm3']<=a['volume_tolerance_mm3']
    assert a['bbox_max_difference_mm']<=a['bbox_tolerance_mm']
