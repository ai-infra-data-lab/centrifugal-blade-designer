from copy import deepcopy
from dataclasses import replace
import numpy as np
import pytest
from blade_designer.geometry.sector_boundary import blade_following_phase
from blade_designer.models.cad import CadExportParameters,SectorBoundaryMode,validate_cad_parameters
from blade_designer.models.parameters import BladeParameters
from blade_designer.fileio.project_io import save_project,load_project


def group(phase=0.,thickness=.02):
    sections=[]
    for z in (0.,10.):
        r=np.linspace(40,80,21);theta=.025*(r-40)+.01*z+phase
        def points(offset):return np.column_stack((r*np.cos(theta+offset),r*np.sin(theta+offset),np.full_like(r,z)))
        sections.append({'ps':points(-thickness),'ss':points(thickness),
                         'le':np.stack((points(-thickness)[0],points(thickness)[0])),
                         'te':np.stack((points(-thickness)[-1],points(thickness)[-1]))})
    return sections


def test_wrapped_main_and_splitter_stay_inside_one_pitch_and_inputs_are_fixed():
    groups=[('main',group(3.)),('splitter',group(3.+np.pi/8))]
    before=deepcopy(groups);phase=blade_following_phase(groups,8)
    for (_,sections),(_,old) in zip(groups,before):
        for section,original in zip(sections,old):
            for role,points in section.items():
                np.testing.assert_array_equal(points,original[role])
                rz=np.column_stack((np.hypot(points[:,0],points[:,1]),points[:,2]))
                low=phase(rz);angle=np.arctan2(points[:,1],points[:,0])
                delta=np.mod(angle-low,2*np.pi)
                assert np.all(delta>0) and np.all(delta<phase.pitch)
    assert phase.sample_margin_rad>0
    assert np.ptp(phase(np.array([[40,0],[80,10]])))>.8


@pytest.mark.parametrize('count',[0,1,2,True,3.5])
def test_invalid_pitch_rejected(count):
    with pytest.raises(ValueError):blade_following_phase([('main',group())],count)


def test_thick_or_ambiguous_blade_sets_are_rejected():
    with pytest.raises(ValueError,match='one-pitch'):
        blade_following_phase([('main',group(thickness=.5))],20)
    broken=group();broken[0]['ps'][0,0]=np.nan
    with pytest.raises(ValueError,match='Invalid blade'):
        blade_following_phase([('main',broken)],8)
    with pytest.raises(ValueError,match='Main blade'):
        blade_following_phase([('splitter',group())],8)


def test_boundary_mode_roundtrip_and_legacy_default(tmp_path):
    p=BladeParameters();path=tmp_path/'project.json';save_project(path,p)
    assert 'cad_export' not in path.read_text(encoding='utf-8')
    assert load_project(path).cad_export.sector_boundary is SectorBoundaryMode.FIXED
    p.cad_export.fillet.hub_radius_mm=1.
    save_project(path,p)
    assert 'sector_boundary' not in path.read_text(encoding='utf-8')
    p.cad_export.sector_boundary=SectorBoundaryMode.BLADE_FOLLOWING
    save_project(path,p)
    assert load_project(path)==p
    with pytest.raises(ValueError):validate_cad_parameters(replace(CadExportParameters(),sector_boundary='bad'))


def test_following_turbogrid_is_rejected_before_creating_output(tmp_path):
    from blade_designer.cad.client import prepare_job
    from blade_designer.cad.pending_job import queue_job
    from blade_designer.models.cad import MechanicalExportScope
    p=BladeParameters();p.cad_export.sector_boundary=SectorBoundaryMode.BLADE_FOLLOWING
    p.cad_export.mechanical_scope=MechanicalExportScope.PERIODIC_SECTOR
    target=tmp_path/'must-not-exist'
    for prepare in (prepare_job,queue_job):
        with pytest.raises(ValueError,match='Mechanical-only'):prepare(p,'both',target)
        assert not target.exists()
    from blade_designer.cad.client import guard_following_export
    p.geometry.vane_count=2
    with pytest.raises(ValueError,match='three'):guard_following_export(p,'mechanical')
    guard_following_export(p,'disk')


def test_existing_study_hash_is_preserved_but_following_setting_is_hashed():
    import json
    from dataclasses import asdict
    from blade_designer.fileio.preview_job import snapshot_text
    p=BladeParameters()
    from tests.legacy_corner_schema import pre_corner_schema
    old=pre_corner_schema(asdict(p));old['cad_export'].pop('sector_boundary')
    expected=json.dumps({'schema_version':'0.4',**old},allow_nan=False,sort_keys=True,
                        default=lambda v:v.value if hasattr(v,'value') else v.item())
    assert snapshot_text(p)==expected
    p.cad_export.sector_boundary=SectorBoundaryMode.BLADE_FOLLOWING
    assert snapshot_text(p)!=expected


def test_existing_cad_snapshot_bytes_and_caller_dictionary_are_preserved():
    import json
    from dataclasses import asdict
    from blade_designer.cad.client import json_text
    p=BladeParameters();current={'schema_version':'0.4',**asdict(p)}
    from tests.legacy_corner_schema import pre_corner_schema
    before=deepcopy(current);old=pre_corner_schema(current);old['cad_export'].pop('sector_boundary')
    expected=json.dumps(old,ensure_ascii=False,allow_nan=False,sort_keys=True,indent=2,
                        default=lambda v:v.value if hasattr(v,'value') else v.item())+'\n'
    assert json_text(current)==expected and current==before


def test_snapshot_compat_does_not_copy_coordinate_or_preview_arrays():
    from blade_designer.fileio.snapshot_compat import canonical_sector_defaults
    from dataclasses import asdict
    points=[[[0.,1.,2.]]]
    value={'triangles':{'PS':points},'sections':points}
    assert canonical_sector_defaults(value) is value
    payload={'blade_rows':[{'parameters':{'cad_export':asdict(CadExportParameters()),'sections':points}}]}
    normalized=canonical_sector_defaults(payload)
    assert 'sector_boundary' not in normalized['blade_rows'][0]['parameters']['cad_export']
    assert normalized['blade_rows'][0]['parameters']['sections'] is points
    assert 'sector_boundary' in payload['blade_rows'][0]['parameters']['cad_export']
