"""Downstream recovery without changing the retained blade or source design."""
from copy import deepcopy
import json
import numpy as np
import pytest
from blade_designer.models.parameters import ImpellerTrimParameters,TipClearanceParameters,SplitterParameters
from blade_designer.models.validation import validate_impeller_trim
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.meridional_segments import sample_meridional
from blade_designer.fileio.project_io import save_project,load_project
from test_analysis_shroud import parameters


@pytest.mark.parametrize('kind',['axial','radial','curved'])
@pytest.mark.parametrize('combined',[False,True])
def test_recovery_preserves_every_blade_and_returns_to_original_outlet(kind,combined):
    p=parameters(kind)
    p.impeller_trim=ImpellerTrimParameters(5)
    if combined:
        p.splitter=SplitterParameters()
        p.tip_clearance=TipClearanceParameters(.5,.8,1.,1.5)
        if kind=='radial':
            p.impeller_trim.diameter_mode='percent';p.impeller_trim.diameter_cut_percent=5
            p.impeller_te_rake_deg=5
    cut=generate_impeller(p)
    p.impeller_trim.shroud_downstream_mode='restore';before=deepcopy(p)
    restored=generate_impeller(p)
    assert p==before
    for attr in ('sections','splitter_sections'):
        for a,b in zip(getattr(cut,attr) or [],getattr(restored,attr) or []):
            for role in ('camber','ps','ss','le','te','master_ps','master_ss','master_le','master_te'):
                np.testing.assert_array_equal(getattr(a,role).xyz,getattr(b,role).xyz)
            np.testing.assert_array_equal(a.beta_m_deg,b.beta_m_deg)
            np.testing.assert_array_equal(a.thickness,b.thickness)
    np.testing.assert_array_equal(restored.hub.r,cut.hub.r)
    np.testing.assert_allclose([restored.shroud.z[-1],restored.shroud.r[-1]],
        [cut.source_geometry.shroud.z[-1],cut.source_geometry.shroud.r[-1]],atol=1e-12)
    np.testing.assert_array_equal([restored.shroud.z[0],restored.shroud.r[0]],
        [cut.shroud.z[0],cut.shroud.r[0]])
    assert np.all(np.diff(restored.shroud.source_m)>0)
    assert restored.analysis_shroud is not None if combined else restored.analysis_shroud is None


def test_axial_recovery_matches_quintic_and_end_tangents():
    p=parameters('axial');p.impeller_trim=ImpellerTrimParameters(10)
    cut=generate_impeller(p)
    p.impeller_trim.shroud_downstream_mode='restore';g=generate_impeller(p)
    # Axial source distance is exactly Z. Rounded TE extent is included.
    start=max(getattr(g.sections[-1],name).z.max() for name in
              ('camber','master_ps','master_ss','master_le','master_te'))
    s=g.shroud.source_m;t=np.clip((s-start)/(100-start),0,1)
    w=t**3*(10-15*t+6*t*t)
    expected=cut.shroud.r[0]+w*(70-cut.shroud.r[0])
    np.testing.assert_allclose(g.shroud.r,expected,atol=1e-10)
    np.testing.assert_allclose(g.shroud.z,s,atol=1e-10)
    assert abs((g.shroud.r[-1]-g.shroud.r[-2])/(s[-1]-s[-2]))<.001
    before=s<start-1e-8
    np.testing.assert_allclose(g.shroud.r[before],cut.shroud.r[0],atol=1e-12)
    # Complete blade Tip still lies on the cut portion, not the recovery.
    assert g.sections[-1].master_te.z.max()<=start+1e-10


def test_old_json_defaults_and_new_roundtrip(tmp_path):
    p=parameters('radial');p.impeller_trim=ImpellerTrimParameters(5)
    path=tmp_path/'case.json';save_project(path,p)
    payload=json.loads(path.read_text())
    assert 'shroud_downstream_mode' not in payload['impeller_trim']
    assert load_project(path)==p
    p.impeller_trim.shroud_downstream_mode='restore';save_project(path,p)
    assert json.loads(path.read_text())['impeller_trim']['shroud_downstream_mode']=='restore'
    assert load_project(path)==p


@pytest.mark.parametrize('value',['bad',None,True,1])
def test_invalid_mode_rejected(value):
    with pytest.raises(ValueError,match='downstream'):
        validate_impeller_trim(ImpellerTrimParameters(shroud_downstream_mode=value))


def test_zero_cut_leaves_original_shape():
    p=parameters('radial');base=generate_impeller(p)
    p.impeller_trim=ImpellerTrimParameters(shroud_downstream_mode='restore')
    g=generate_impeller(p)
    np.testing.assert_array_equal(g.shroud.r,base.shroud.r)
    assert g.source_geometry is None


def test_no_downstream_room_rejects_and_protects_saved_file(tmp_path):
    from blade_designer.geometry.impeller_trim import _restore_downstream
    p=parameters('axial')
    p.impeller_trim=ImpellerTrimParameters(5)
    g=generate_impeller(p)
    # Boundary unit check: a retained Tip point reaches the casing outlet.
    g.sections[-1].camber.z[-1]=g.shroud.z[-1]
    with pytest.raises(ValueError,match='downstream interval'):
        _restore_downstream(g.source_geometry,g)
    # Persisted invalid options must fail before replacing an existing file.
    p.impeller_trim.shroud_downstream_mode='bad'
    path=tmp_path/'existing.json';path.write_bytes(b'original')
    with pytest.raises(ValueError,match='downstream'):
        save_project(path,p)
    assert path.read_bytes()==b'original'


def test_restored_owned_wall_preview_uses_original_mapping():
    from blade_designer.geometry.row_domain import preview_wall_chunks
    p=parameters('curved');p.impeller_trim=ImpellerTrimParameters(5,shroud_downstream_mode='restore')
    g=generate_impeller(p)
    identifier=next(s.blade_row for s in p.shroud.segments if s.blade_row is not None)
    chunks=preview_wall_chunks(p,g,identifier)
    assert chunks['shroud']
    assert all(np.isfinite(chunk.r).all() for chunk in chunks['shroud'])
    source=g.shroud.source_boundaries
    np.testing.assert_allclose(sample_meridional(g.shroud,
        np.interp(source,g.shroud.source_m,g.shroud.m))[-1],
        [g.source_geometry.shroud.z[-1],g.source_geometry.shroud.r[-1]])


@pytest.mark.parametrize('extension',['csv','txt'])
def test_wall_output_matches_restored_display_and_existing_export_guards(extension,tmp_path):
    from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions,prepare_coordinate_csv
    from blade_designer.fileio.geometry_source import geometry_source
    from blade_designer.fileio.turbogrid_export import export_turbogrid
    from blade_designer.cad.client import prepare_job
    from test_wall_coordinate_output import read
    p=parameters('radial');p.impeller_trim=ImpellerTrimParameters(5,shroud_downstream_mode='restore')
    g=generate_impeller(p)
    options=CoordinateCsvOptions(('r_mm','z_mm'),include_blades=False,include_shroud=True,extension=extension)
    rows=read(prepare_coordinate_csv(g,geometry_source(p,'meridional_3d'),options)['coordinates.'+extension],extension)
    np.testing.assert_allclose([[float(row['r_mm']),float(row['z_mm'])] for row in rows],
                               np.column_stack((g.shroud.r,g.shroud.z)),atol=1e-12)
    target=tmp_path/'existing';target.mkdir();sentinel=target/'profile.curve';sentinel.write_bytes(b'original')
    with pytest.raises(ValueError,match='trim'):export_turbogrid(target,p)
    assert list(target.iterdir())==[sentinel] and sentinel.read_bytes()==b'original'
    with pytest.raises(ValueError,match='trim'):prepare_job(p,job_directory=tmp_path/'cad')
    assert not (tmp_path/'cad').exists()
