from copy import deepcopy
from pathlib import Path
import pytest
import sys
from blade_designer.fileio.project_io import load_project
from blade_designer.models.parameters import BladeParameters,TipClearanceParameters
from blade_designer.models.cad import MechanicalExportScope
from blade_designer.fileio import export_readiness as er


@pytest.fixture(autouse=True)
def backend_executable(monkeypatch):
    # Existence only, never evidence of an installed/runnable CAD kernel.
    monkeypatch.setattr(er,'backend_python',lambda:Path(sys.executable))


def route(report,name):return next(r for r in report.routes if r.name==name)


def test_default_reports_splitter_and_domain_without_creating_files(monkeypatch):
    p=load_project(Path(__file__).resolve().parents[1]/'blade_designer/defaults/default_project.json')
    p.active_blade_row=next(r.identifier for r in p.blade_rows if r.kind=='impeller')
    before=deepcopy(p)
    def forbidden(*args,**kwargs):raise AssertionError('Readiness must not write files.')
    monkeypatch.setattr(Path,'mkdir',forbidden)
    monkeypatch.setattr(Path,'write_text',forbidden)
    monkeypatch.setattr(Path,'write_bytes',forbidden)
    report=er.assess_exports(p,forbidden)
    profile=route(report,'Profile Points')
    assert profile.status=='BLOCKED'
    assert 'domain' in {c.code for c in profile.checks if c.state=='BLOCKED'}
    assert any(c.code=='splitter' and c.state=='PASS' for c in profile.checks)
    assert report.row_name=='Impeller' and p==before
    assert route(report,'Mechanical STEP').status=='BLOCKED'
    assert any(c.code=='kernel' and c.state=='NOT_TESTED' for c in route(report,'Mechanical STEP').checks)


def test_blade_only_inputs_ready_does_not_claim_fillet_or_ansys_pass():
    p=BladeParameters();p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    called=[];r=er.assess_exports(p,lambda data:called.append(data))
    assert route(r,'Profile Points').status=='INPUTS_READY'
    assert route(r,'Mechanical STEP').status=='INPUTS_READY'
    assert len(called)==1 and called[0]==p
    assert 'not run' in r.note
    assert any(c.state=='NOT_TESTED' for c in route(r,'Mechanical STEP').checks)


def test_stator_selection_uses_own_snapshot_and_cad_remains_unsupported():
    p=load_project(Path(__file__).resolve().parents[1]/'blade_designer/defaults/default_project.json')
    assert p.active_blade_row=='row-3'
    r=er.assess_exports(p,lambda data:None)
    assert r.row_name=='RC' and r.kind=='diffuser'
    assert route(r,'Profile Points').status=='INPUTS_READY'
    assert route(r,'Mechanical STEP').status=='BLOCKED'
    assert route(r,'TurboGrid CAD').status=='BLOCKED'


def test_formatting_error_and_backend_absence_are_distinct(monkeypatch):
    p=BladeParameters();p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    def no_backend():raise er.BackendUnavailableError('not installed')
    def collapsed(data):raise ValueError('Collapsed at selected output precision')
    monkeypatch.setattr(er,'backend_python',no_backend)
    r=er.assess_exports(p,collapsed)
    assert any(c.code=='serialized' and c.state=='BLOCKED' for c in route(r,'Profile Points').checks)
    assert any(c.code=='backend' and c.state=='BLOCKED' for c in route(r,'Mechanical STEP').checks)


def test_positive_gap_only_blocks_turbogrid_cad():
    from test_tip_clearance import axial_parameters
    p=axial_parameters();p.tip_clearance=TipClearanceParameters(1.,2.)
    p.cad_export.mechanical_scope=MechanicalExportScope.BLADE_ONLY
    r=er.assess_exports(p,lambda data:None)
    assert route(r,'Profile Points').status=='INPUTS_READY'
    assert route(r,'Mechanical STEP').status=='INPUTS_READY'
    assert any(c.code=='clearance' and c.state=='BLOCKED' for c in route(r,'TurboGrid CAD').checks)


def test_trim_is_reported_without_running_unsupported_geometry(monkeypatch):
    from blade_designer.models.parameters import ImpellerTrimParameters
    p=BladeParameters();p.impeller_trim=ImpellerTrimParameters(shroud_area_cut_percent=5)
    def forbidden(*args):raise AssertionError('Unsupported trim export should not generate a derivative')
    monkeypatch.setattr(er,'generate_impeller',forbidden)
    r=er.assess_exports(p,forbidden)
    assert all(item.status=='BLOCKED' for item in r.routes)
    assert all(any(c.code=='trim' and c.state=='BLOCKED' for c in item.checks) for item in r.routes)


def test_disabled_cad_and_invalid_selection_are_clear():
    p=BladeParameters();p.cad_export.mechanical_enabled=False;p.cad_export.turbogrid_enabled=False
    r=er.assess_exports(p,lambda data:None)
    assert route(r,'Profile Points').status=='INPUTS_READY'
    assert all(route(r,name).status=='BLOCKED' for name in ('Mechanical STEP','TurboGrid CAD'))
    p.active_blade_row='missing'
    r=er.assess_exports(p,lambda data:None)
    assert r.kind=='unknown' and all(item.status=='BLOCKED' for item in r.routes)


def test_real_profile_preparation_is_nonwriting_and_reports_snapshot(monkeypatch):
    from blade_designer.fileio.turbogrid_export import prepare_turbogrid_export
    p=load_project(Path(__file__).resolve().parents[1]/'blade_designer/defaults/default_project.json')
    before=deepcopy(p)
    def forbidden(*args,**kwargs):raise AssertionError('No files may be created by readiness')
    monkeypatch.setattr(Path,'mkdir',forbidden)
    monkeypatch.setattr(Path,'open',forbidden)
    report=er.assess_exports(p)
    assert route(report,'Profile Points').status=='INPUTS_READY'
    assert any(c.code=='serialized' and c.state=='PASS' for c in route(report,'Profile Points').checks)
    assert len(report.snapshot_hash)==64 and p==before
    p.geometry.vane_count+=1
    assert er.assess_exports(p).snapshot_hash!=report.snapshot_hash


def test_stale_provisional_disk_is_blocked_without_modifying_dimensions():
    from test_tip_clearance import axial_parameters
    from blade_designer.geometry.provisional_disk import make_provisional_disk
    p=axial_parameters();p.cad_export.disk=make_provisional_disk(p)
    p.cad_export.disk.front_end_m_mm=1.
    before=deepcopy(p)
    report=er.assess_exports(p,lambda data:None)
    assert p==before
    for name in ('Mechanical STEP','TurboGrid CAD'):
        assert any(c.code=='disk_extent' and c.state=='BLOCKED' for c in route(report,name).checks)
