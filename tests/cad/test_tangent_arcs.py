"""Native BREP/STEP acceptance of the opt-in G1 circular edge geometry."""
from blade_designer.models.parameters import EdgeType
from blade_designer.models.cad import MechanicalExportScope
from .conftest import sample_parameters,run_job


def test_tangent_arc_blade_is_closed_valid_and_roundtrips_step(tmp_path):
    p=sample_parameters()
    p.cad_export.disk.backside=None;p.cad_export.disk.bore_radius_mm=None
    p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    for section in p.sections:
        section.edge_parameters.le_type=section.edge_parameters.te_type=EdgeType.TANGENT_CIRCULAR
    result=run_job(p,tmp_path/'tangent','mechanical');r=result['report']
    assert r['solid_validity']=='PASS',r.get('error')
    assert r['cad_surface_status']=='PASS'
    assert r['checks']['result']['solid_count']==1
    assert r['artifacts']['mechanical']['roundtrip']['main']['status']=='PASS'
    assert all(e<=p.cad_export.surface_tolerance_mm for e in r['checks']['blade_solids']['main']['master_deviation_mm'].values())
