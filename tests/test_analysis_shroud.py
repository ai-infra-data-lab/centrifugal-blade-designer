"""Fixed physical blade, normal-offset analysis casing and protected exports."""
from copy import deepcopy
from dataclasses import replace
import csv, io, json
from pathlib import Path
import numpy as np
import pytest
from blade_designer.models.parameters import TipClearanceParameters, SplitterParameters, ImpellerTrimParameters
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.tip_clearance import _frame
from blade_designer.fileio.project_io import save_project, load_project
from blade_designer.fileio.turbogrid_export import prepare_turbogrid_export, export_turbogrid
from blade_designer.fileio.coordinate_csv import CoordinateCsvOptions, prepare_coordinate_csv
from blade_designer.fileio.geometry_source import geometry_source
from blade_designer.geometry.row_domain import preview_wall_chunks
from test_tip_clearance import axial_parameters
from test_impeller_te_rake import radial_parameters


def parameters(kind='radial'):
    p=axial_parameters() if kind=='axial' else radial_parameters()
    if kind=='curved':
        p=load_project(Path(__file__).parents[1]/'blade_designer/defaults/default_project.json')
        from blade_designer.models.blade_rows import row_parameters
        p=row_parameters(p,p.blade_rows[0])
    p.resolution.wall_points=501;p.resolution.profile_points=301;p.resolution.edge_points=31
    p.resolution.mean_points=501;p.resolution.area_points=21
    return p


@pytest.mark.parametrize('kind',['axial','radial','curved'])
@pytest.mark.parametrize('drawing,analysis',[(0.,(1.,2.)),(.5,(1.,2.)),(1.,(0.,0.)),(1.,(.2,.8))])
def test_fixed_blades_splitter_and_exact_common_normal_gap(kind,drawing,analysis):
    p=parameters(kind);p.splitter=SplitterParameters();p.tip_clearance=TipClearanceParameters(drawing,drawing)
    base=generate_impeller(p)
    p.tip_clearance.analysis_le_mm,p.tip_clearance.analysis_te_mm=analysis
    before=deepcopy(p);g=generate_impeller(p);a=g.analysis_shroud
    assert p==before
    for groups in ('sections','splitter_sections'):
        for old,new in zip(getattr(base,groups),getattr(g,groups)):
            for role in ('camber','ps','ss','le','te','master_ps','master_ss','master_le','master_te'):
                np.testing.assert_array_equal(getattr(old,role).xyz,getattr(new,role).xyz)
            np.testing.assert_array_equal(old.beta_m_deg,new.beta_m_deg)
            np.testing.assert_array_equal(old.thickness,new.thickness)
    for wall in ('hub','shroud'):
        np.testing.assert_array_equal(getattr(base,wall).r,getattr(g,wall).r)
        np.testing.assert_array_equal(getattr(base,wall).z,getattr(g,wall).z)
    _,normal,_=_frame(g.hub,g.shroud,a.drawing_m)
    actual=np.column_stack((a.tip_z-a.wall.z,a.tip_r-a.wall.r))
    expected=np.interp(a.drawing_m,[a.le_drawing_m,a.te_drawing_m],analysis)
    np.testing.assert_allclose(actual,expected[:,None]*normal,atol=1e-12)
    np.testing.assert_array_equal(a.clearance_mm,expected)


def test_axial_analytic_casing_moves_outward_not_blade():
    p=parameters('axial');p.tip_clearance=TipClearanceParameters(1,2,2,3)
    g=generate_impeller(p)
    np.testing.assert_allclose(g.analysis_shroud.wall.r,71,atol=1e-10)
    np.testing.assert_allclose(g.shroud.r,70,atol=1e-12)


@pytest.mark.parametrize('analysis',[(1.,2.),(0.,0.)])
@pytest.mark.parametrize('splitter',[False,True])
def test_turbogrid_selects_analysis_shroud_with_original_physical_tip(analysis,splitter):
    p=parameters();p.tip_clearance=TipClearanceParameters(.5,.5,*analysis)
    if splitter:p.splitter=SplitterParameters()
    g=generate_impeller(p);before=deepcopy(p)
    names,contents=prepare_turbogrid_export(p)
    shroud=np.loadtxt(io.BytesIO(contents[names[1]]))
    a=g.analysis_shroud
    expected=np.column_stack((np.interp(np.linspace(0,a.wall.length,p.shroud.export_points),a.wall.m,a.wall.r),
                              np.zeros(p.shroud.export_points),np.interp(np.linspace(0,a.wall.length,p.shroud.export_points),a.wall.m,a.wall.z)))
    np.testing.assert_allclose(shroud,expected,rtol=1e-5,atol=1e-5)
    text=contents[names[2]].decode()
    assert text.count('# Shroud_extension') == ((2 if splitter else 1) if any(analysis) else 0)
    assert b'Analysis Shroud selected' in contents['BladeGen.inf']
    assert p==before


def test_legacy_json_optional_fields_and_invalid_partial_setting(tmp_path):
    p=parameters();p.tip_clearance=TipClearanceParameters(.5,.7)
    target=tmp_path/'legacy.json';save_project(target,p)
    assert json.loads(target.read_text())['tip_clearance']=={'le_mm':.5,'te_mm':.7}
    assert load_project(target)==p
    p.tip_clearance.analysis_le_mm=.3;p.tip_clearance.analysis_te_mm=.6
    save_project(target,p);assert load_project(target)==p
    original=target.read_bytes();p.tip_clearance.analysis_te_mm=None
    with pytest.raises(ValueError):save_project(target,p)
    assert target.read_bytes()==original


@pytest.mark.parametrize('values',[(None,1.),(-1.,1.),(float('nan'),1.),(1.,float('inf'))])
def test_bad_values_protect_existing_and_new_exports(values,tmp_path):
    p=parameters();files=export_turbogrid(tmp_path/'case',p);before={f:f.read_bytes() for f in files}
    p.tip_clearance=TipClearanceParameters(1.,1.,*values)
    for directory in (tmp_path/'case',tmp_path/'new'):
        with pytest.raises(ValueError):export_turbogrid(directory,p)
    assert {f:f.read_bytes() for f in files}==before and not (tmp_path/'new').exists()


@pytest.mark.parametrize('extension',['csv','txt'])
def test_csv_txt_both_casings_preserve_identity_and_ownership(extension):
    p=parameters();p.tip_clearance=TipClearanceParameters(.5,.5,1.,2.)
    g=generate_impeller(p);source=geometry_source(p,'meridional_3d')
    options=CoordinateCsvOptions(('z_mm','r_mm'),include_blades=False,include_shroud=True,
                                 wall_layout='separate',extension=extension,shroud_source='both')
    data=prepare_coordinate_csv(g,source,options,wall_chunks=preview_wall_chunks(p,g,None))
    assert set(data)=={'shroud.'+extension,'analysis_shroud.'+extension}
    for name,wall in [('shroud',g.shroud),('analysis_shroud',g.analysis_shroud.wall)]:
        rows=list(csv.DictReader(io.StringIO(data[name+'.'+extension].decode('utf-8-sig')),delimiter='\t' if extension=='txt' else ','))
        assert {r['blade_set'] for r in rows}=={name}
        np.testing.assert_allclose([[float(r[k]) for k in ('z_mm','r_mm')] for r in rows],np.column_stack((wall.z,wall.r)),rtol=1e-13,atol=1e-12)


def test_trim_updates_analysis_wall_after_physical_cut():
    p=parameters();p.tip_clearance=TipClearanceParameters(.5,.5,1.,2.)
    p.impeller_trim=ImpellerTrimParameters(shroud_area_cut_percent=5.)
    g=generate_impeller(p)
    assert g.trim_report and g.analysis_shroud is not None
    assert hasattr(g.analysis_shroud.wall,'source_boundaries')
    assert len(g.analysis_shroud.wall.source_boundaries)==len(p.shroud.segments)+1


def test_curved_trim_uses_the_same_continuous_vertex_normals_as_drawing_tip():
    p=parameters('curved');p.tip_clearance=TipClearanceParameters(.5,1.)
    p.impeller_trim=ImpellerTrimParameters(shroud_area_cut_percent=5.)
    drawing=generate_impeller(p)
    p.tip_clearance.analysis_le_mm=1.;p.tip_clearance.analysis_te_mm=1.5
    g=generate_impeller(p);a=g.analysis_shroud
    from blade_designer.geometry.impeller_trim import _Boundary
    vertex=_Boundary(np.column_stack((g.shroud.z,g.shroud.r)),g.hub).normals
    n=np.column_stack([np.interp(a.drawing_m,g.shroud.m,vertex[:,i]) for i in (0,1)])
    n/=np.linalg.norm(n,axis=1)[:,None]
    np.testing.assert_allclose(np.column_stack((a.tip_z-a.wall.z,a.tip_r-a.wall.r)),a.clearance_mm[:,None]*n,atol=1e-12)
    for old,new in zip(drawing.sections,g.sections):
        for key in ('camber','master_le','master_ps','master_te','master_ss'):
            np.testing.assert_array_equal(getattr(old,key).xyz,getattr(new,key).xyz)


def test_mechanical_job_uses_drawing_blade_and_casing(tmp_path):
    from blade_designer.cad.client import prepare_job
    p=parameters();p.tip_clearance=TipClearanceParameters(.5,.5)
    first=prepare_job(p,job_directory=tmp_path/'drawing')
    p.tip_clearance.analysis_le_mm=1;p.tip_clearance.analysis_te_mm=2
    second=prepare_job(p,job_directory=tmp_path/'analysis')
    with np.load(first/'geometry.npz') as a,np.load(second/'geometry.npz') as b:
        assert a.files==b.files
        for key in a.files:np.testing.assert_array_equal(a[key],b[key])
    a=json.loads((first/'request.json').read_text());b=json.loads((second/'request.json').read_text())
    assert a['shroud_segments']==b['shroud_segments']


def test_turbogrid_rejects_stale_analysis_row_even_when_drawing_gap_is_zero():
    from blade_designer.models.blade_rows import initial_rows
    p=parameters();p.tip_clearance=TipClearanceParameters(0,0,1,2)
    p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
    p.tip_clearance.analysis_le_mm=3
    with pytest.raises(ValueError,match='snapshot'):prepare_turbogrid_export(p)


def test_analysis_wall_export_keeps_selected_ownership_interval():
    from blade_designer.models.blade_rows import initial_rows
    from blade_designer.models.meridional import LineSegmentParameters
    p=parameters();p.tip_clearance=TipClearanceParameters(.5,.5,1,2)
    for wall in (p.hub,p.shroud):
        wall.segments=[LineSegmentParameters(90,blade_row='row-1'),LineSegmentParameters(10,blade_row='row-2')]
    p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
    names,contents=prepare_turbogrid_export(p)
    points=np.loadtxt(io.BytesIO(contents[names[1]]))
    np.testing.assert_allclose(points[[0,-1],0],[50,140],atol=1e-8)
    assert points[:,0].max()<150


@pytest.mark.parametrize('action',['turbogrid','both'])
def test_analysis_only_gap_rejects_unsupported_turbogrid_cad_before_job(action,tmp_path):
    from blade_designer.cad.client import prepare_job
    p=parameters();p.tip_clearance=TipClearanceParameters(0,0,1,2)
    p.cad_export.turbogrid_enabled=True
    with pytest.raises(ValueError,match='not supported'):
        prepare_job(p,action=action,job_directory=tmp_path/'job')
    assert not (tmp_path/'job').exists()
