from copy import deepcopy
from pathlib import Path
import json,subprocess,sys
import pytest
from blade_designer.cad.client import prepare_job,backend_python,ROOT,publish_job
from blade_designer.models.parameters import BladeParameters,BladeSection,DistributionPoint
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.models.cad import MechanicalExportScope


def sample_parameters():
    p=BladeParameters();p.hub=MeridionalCurveParameters(0,50,90,[LineSegmentParameters(200)])
    p.shroud=MeridionalCurveParameters(80,50,90,[LineSegmentParameters(200)])
    p.sections.insert(1,BladeSection(.5));p.geometry.vane_count=2
    for section in p.sections:
        section.blade_angle.points=[DistributionPoint(0,15),DistributionPoint(1,25)]
        section.thickness.points=[DistributionPoint(0,20),DistributionPoint(.35,24),DistributionPoint(1,20)]
    p.cad_export.disk.backside=MeridionalCurveParameters(-40,250,-90,[LineSegmentParameters(230)])
    p.cad_export.disk.bore_radius_mm=20
    return p


def run_job(p,directory,action):
    try:python=backend_python()
    except Exception as exc:pytest.skip("Optional native CAD backend unavailable: "+str(exc))
    job=prepare_job(p,action,directory)
    run=subprocess.run([str(python),"-X","utf8","-m","blade_designer.cad.worker",str(job.resolve())],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=900)
    (job/'test_process.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    assert run.returncode==0,run.stdout+run.stderr
    return {"params":p,"job":job,"report":json.loads((job/'result.json').read_text(encoding='utf-8'))}


@pytest.fixture(scope='session')
def native_assembly(tmp_path_factory):
    p=sample_parameters();p.cad_export.mechanical_scope=MechanicalExportScope.PERIODIC_SECTOR
    return run_job(p,tmp_path_factory.mktemp('native_assembly')/'job','both')


@pytest.fixture(scope='session')
def native_blade(tmp_path_factory):
    p=sample_parameters();p.cad_export.disk.backside=None;p.cad_export.disk.bore_radius_mm=None
    p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    return run_job(p,tmp_path_factory.mktemp('native_blade')/'job','mechanical')


@pytest.fixture(scope='session')
def native_failure(tmp_path_factory):
    p=sample_parameters();p.shroud.start_z=2.
    return run_job(p,tmp_path_factory.mktemp('native_failure')/'job','mechanical')
