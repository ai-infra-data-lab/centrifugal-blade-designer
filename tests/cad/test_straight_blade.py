from blade_designer.models.parameters import DistributionPoint
from .conftest import sample_parameters,run_job


def test_straight_blade_small_root_fillet_fixture_a(tmp_path):
    p=sample_parameters();p.cad_export.fillet.hub_radius_mm=1.
    for section in p.sections:
        section.blade_angle.points=[DistributionPoint(0,0),DistributionPoint(1,0)]
        section.thickness.points=[DistributionPoint(0,6),DistributionPoint(1,6)]
    result=run_job(p,tmp_path/'straight','mechanical');r=result['report']
    assert r['overall']=='PASS',r.get('error')
    assert r['checks']['fillet']['main']['fillet_radius_mm']==1.
    step=r['artifacts']['mechanical']['roundtrip']
    assert step['status']=='PASS'
    assert all(face['status']=='PASS' for face in step['fillet_after_step']['faces'])
