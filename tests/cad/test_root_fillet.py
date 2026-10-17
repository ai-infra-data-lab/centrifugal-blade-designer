def test_real_r8_faces_and_measured_radii_before_and_after_step(native_assembly):
    r=native_assembly['report'];assert r['fillet_status']=='PASS',r.get('error')
    f=r['checks']['fillet']['main'];assert f['fillet_radius_mm']==8 and f['fillet_face_count']>=4
    export=r['artifacts']['mechanical']['roundtrip']
    for name in ('fillet_before_step','fillet_after_step'):
        assert export[name]['requested_radius_mm']==8
        assert export[name]['faces']
        assert all(face['status']=='PASS' for face in export[name]['faces'])
        assert export[name]['global_exact_radius']=='NOT_TESTED'
