from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import csv, hashlib, io
import numpy as np
import pytest
from blade_designer.fileio.geometry_source import geometry_source
from blade_designer.fileio.row_xyz_csv import prepare_row_xyz_csv, export_row_xyz_csv
from blade_designer.fileio.project_io import load_project
from blade_designer.cad.client import json_text
from blade_designer.models.blade_rows import row_parameters
from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
from blade_designer.geometry.section_measurements import measure_section

TEMPLATE=Path(__file__).resolve().parents[1]/'blade_designer/defaults/default_project.json'


@pytest.mark.parametrize('identifier',['row-1','row-2','row-3'])
def test_every_xyz_csv_master_matches_generated_main_and_splitter_sections(identifier):
    project=load_project(TEMPLATE);project.active_blade_row=identifier
    row=next(r for r in project.blade_rows if r.identifier==identifier)
    p=row_parameters(project,row);before=deepcopy(project)
    g=generate_impeller(p) if row.kind=='impeller' else generate_diffuser_3d(p)
    source=geometry_source(project,'meridional_3d')
    rows=list(csv.DictReader(io.StringIO(prepare_row_xyz_csv(g,source).decode('utf-8-sig'))))
    expected=[]
    for name,sections in [('main',g.sections),('splitter',g.splitter_sections)]:
        for section in sections or []:
            for role in ('LE','PS','TE','SS'):
                c=getattr(section,'master_'+role.lower())
                for index,xyz in enumerate(c.xyz):expected.append((name,section.span,role,index,xyz))
    assert len(rows)==len(expected)
    for data,(name,span,role,index,xyz) in zip(rows,expected):
        assert (data['blade_set'],float(data['span']),data['segment'],int(data['index']))==(name,span,role,index)
        np.testing.assert_allclose([float(data[k]) for k in ['x_mm','y_mm','z_mm']],xyz,rtol=1e-13,atol=1e-12)
        assert data['row_id']==identifier and data['row_name']==row.name and data['snapshot_hash']==source.snapshot_hash
    assert source.snapshot_hash==hashlib.sha256(json_text({'schema_version':'0.4',**asdict(project)}).encode('utf-8')).hexdigest()
    assert project==before
    if identifier=='row-3':assert all(float(r['z_mm'])>70 for r in rows)


def test_identity_distinguishes_engine_row_rename_and_snapshot_without_mutating_design():
    p=load_project(TEMPLATE);before=deepcopy(p)
    actual=geometry_source(p,'meridional_3d');legacy=geometry_source(p,'legacy_radial_2d')
    assert actual.snapshot_hash==legacy.snapshot_hash and actual.engine!=legacy.engine
    assert p==before and actual.row_name=='RC'
    p.blade_rows[-1].name='戻り流路, RC'
    assert geometry_source(p,'meridional_3d').snapshot_hash!=actual.snapshot_hash
    p.active_blade_row='missing'
    with pytest.raises(ValueError):geometry_source(p,'meridional_3d')


def test_invalid_or_wrong_source_preserves_existing_xyz_csv(tmp_path):
    p=load_project(TEMPLATE);g=generate_diffuser_3d(row_parameters(p,p.blade_rows[-1]));source=geometry_source(p,'meridional_3d')
    target=tmp_path/'model.csv';target.write_bytes(b'previous valid output')
    with pytest.raises(ValueError):export_row_xyz_csv(target,g,replace(source,engine='legacy_radial_2d'))
    g.sections[-1].master_ps.z[-1]=float('nan')
    with pytest.raises(ValueError):export_row_xyz_csv(target,g,source)
    assert target.read_bytes()==b'previous valid output' and list(tmp_path.iterdir())==[target]


def test_csv_install_failure_keeps_existing_file_and_removes_only_temporary(tmp_path,monkeypatch):
    from blade_designer.fileio import row_xyz_csv
    p=load_project(TEMPLATE);g=generate_diffuser_3d(row_parameters(p,p.blade_rows[-1]));source=geometry_source(p,'meridional_3d')
    target=tmp_path/'model.csv';target.write_bytes(b'previous')
    def locked(*args):raise PermissionError('locked destination')
    monkeypatch.setattr(row_xyz_csv.os,'replace',locked)
    with pytest.raises(PermissionError):export_row_xyz_csv(target,g,source)
    assert target.read_bytes()==b'previous' and list(tmp_path.iterdir())==[target]


@pytest.mark.parametrize('variant',['base','rake','clearance','trim','splitter','splitter_trim'])
def test_measurements_and_xyz_csv_follow_actual_rake_gap_and_derived_sections(variant):
    from test_impeller_te_rake import radial_parameters
    from blade_designer.models.parameters import TipClearanceParameters,ImpellerTrimParameters,SplitterParameters,RotationDirection
    p=radial_parameters();p.rotation_direction=RotationDirection.CW
    if variant=='rake':p.impeller_te_rake_deg=15.
    if variant=='clearance':p.tip_clearance=TipClearanceParameters(.5,1.)
    if 'trim' in variant:p.impeller_trim=ImpellerTrimParameters(shroud_area_cut_percent=5.)
    if 'splitter' in variant:p.splitter=SplitterParameters()
    before=deepcopy(p);g=generate_impeller(p)
    source=geometry_source(p,'meridional_3d',variant='derived' if g.trim_report else 'base')
    rows=list(csv.DictReader(io.StringIO(prepare_row_xyz_csv(g,source).decode('utf-8-sig'))))
    for group,sections in [('main',g.sections),('splitter',g.splitter_sections)]:
        for section in sections or []:
            m=measure_section(section,p.geometry.vane_count)
            np.testing.assert_array_equal(m.radii,section.camber.r)
            assert np.all(np.isfinite(m.ps_curvature_xyz)) and m.camber_length_xyz>=m.camber_chord_xyz-1e-10
            data=[r for r in rows if r['blade_set']==group and float(r['span'])==section.span and r['segment']=='PS']
            np.testing.assert_allclose([[float(r[k]) for k in ('x_mm','y_mm','z_mm')] for r in data],section.master_ps.xyz,rtol=1e-13,atol=1e-12)
    assert p==before
