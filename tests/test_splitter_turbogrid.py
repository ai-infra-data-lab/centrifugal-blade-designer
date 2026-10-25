"""Two-blade XYZ export, official ## separators and protected publication."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import hashlib,json,os
import numpy as np
import pytest
from blade_designer.fileio import turbogrid_export as tg
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.span_extension import extend_tip_to_shroud
from blade_designer.models.parameters import SplitterParameters,TipClearanceParameters,RotationDirection,EdgeType
from blade_designer.models.blade_rows import initial_rows
from test_impeller_te_rake import radial_parameters


def blade_sets(path):
    """Read the official radcomp structure independently of the exporter."""
    blades=[]
    for line in path.read_text().splitlines():
        if line.startswith('## '):blades.append((line[3:],[]))
        elif line.startswith('# '):blades[-1][1].append((line[2:],[],{}))
        elif line.strip():
            fields=line.split();section=blades[-1][1][-1]
            assert len(fields) in (3,4)
            section[1].append([float(v) for v in fields[:3]])
            if len(fields)==4:section[2][len(section[1])-1]=fields[3]
    return [(name,[(label,np.array(xyz),markers) for label,xyz,markers in sections]) for name,sections in blades]


@pytest.mark.parametrize('direction',list(RotationDirection))
@pytest.mark.parametrize('edge',[EdgeType.CUTOFF,EdgeType.ELLIPTICAL])
@pytest.mark.parametrize('independent',[False,True])
@pytest.mark.parametrize('clearance',[False,True])
@pytest.mark.parametrize('axis,order,unit,scale',[
    ('Z',[0,1,2],'MM',1.),('X',[2,0,1],'CM',.1),('Y',[1,2,0],'M',.001)])
def test_main_and_splitter_match_display_sections_and_casing(tmp_path,direction,edge,independent,clearance,axis,order,unit,scale):
    p=radial_parameters(edge);p.rotation_direction=direction;p.impeller_te_rake_deg=20
    p.splitter=SplitterParameters(.35,.65,.37,.8)
    for section in p.sections:section.edge_parameters.te_ellipse_ratio=1.5
    if independent:
        p.splitter.sections=deepcopy(p.sections)
        for section in p.splitter.sections:
            section.blade_angle.points[-1].value+=4
            section.thickness.points[-1].value*=.7
    if clearance:p.tip_clearance=TipClearanceParameters(.5,1.)
    p.turbogrid.rotation_axis=axis;p.turbogrid.geometry_unit=unit;p.export.significant_digits=15
    p.turbogrid.profile_curve_filename='blade-set.crv'
    before=deepcopy(p);g=generate_impeller(p)
    files=tg.export_turbogrid(tmp_path/'case',p);parsed=blade_sets(files[2])
    assert p==before and len(files)==4
    assert [name for name,_ in parsed]==['Main','Splitter']
    for (_,actual),sections in zip(parsed,(g.sections,g.splitter_sections)):
        expected_sections=sections+([extend_tip_to_shroud(replace(g,sections=sections))] if clearance else [])
        assert len(actual)==len(expected_sections)
        assert [label for label,_,_ in actual]==(['Hub','Span_0.5','Tip_clearance','Shroud_extension'] if clearance else ['Hub','Span_0.5','Tip'])
        for (_,xyz,markers),section in zip(actual,expected_sections):
            expected,expected_markers=tg.closed_profile(section)
            np.testing.assert_allclose(xyz,expected[:,order]*scale,rtol=6e-15,atol=1e-12*scale)
            np.testing.assert_array_equal(xyz[0],xyz[-1])
            assert np.all(np.linalg.norm(np.diff(xyz,axis=0),axis=1)>0)
            assert markers==expected_markers and sorted(markers.values())==['le','te']
        assert len({len(xyz) for _,xyz,_ in actual})==1
    inf=files[3].read_text()
    assert f'Number of Blade Sets: {p.geometry.vane_count}\n' in inf
    assert 'Number of Blades Per Set: 2\n' in inf
    for i in (0,1):
        assert f'Blade {i} LE: EllipseEnd' in inf
        assert f'Blade {i} TE: '+('CutOffEnd' if edge==EdgeType.CUTOFF else 'EllipseEnd') in inf
    assert ('Right Handed' if direction.sign==1 else 'Left Handed') in inf
    if clearance:assert 'Profile Number 3' in inf and 'both Main and Splitter' in inf
    path=tmp_path/'project.json';save_project(path,p);assert load_project(path)==p


def test_switching_splitter_on_and_off_keeps_main_and_user_files(tmp_path):
    p=radial_parameters();case=tmp_path/'case';original=tg.export_turbogrid(case,p)
    main=original[2].read_bytes();walls=[f.read_bytes() for f in original[:2]]
    (case/'notes.txt').write_bytes(b'user notes')
    p.splitter=SplitterParameters();files=tg.export_turbogrid(case,p)
    parsed=blade_sets(files[2]);assert parsed[0][0]=='Main'
    assert files[2].read_bytes().split(b'## Splitter')[0]==b'## Main'+os.linesep.encode()+main
    p.splitter=None;files=tg.export_turbogrid(case,p)
    assert files[2].read_bytes()==main and [f.read_bytes() for f in files[:2]]==walls
    assert (case/'notes.txt').read_bytes()==b'user notes'


@pytest.mark.parametrize('invalid',['settings','precision','snapshot','missing','span','domain','collapsed','extension'])
def test_invalid_splitter_cannot_replace_existing_output(tmp_path,monkeypatch,invalid):
    p=radial_parameters();p.splitter=SplitterParameters();case=tmp_path/'case'
    tg.export_turbogrid(case,p);(case/'notes.txt').write_bytes(b'original')
    before={f.name:f.read_bytes() for f in case.iterdir()}
    if invalid=='settings':p.splitter.hub_start_fraction=1.
    elif invalid=='precision':p.export.significant_digits=1
    elif invalid=='snapshot':
        p.blade_rows=initial_rows(p);p.active_blade_row='row-1';p.blade_rows[0].parameters.splitter=None
    elif invalid=='extension':
        p.tip_clearance=TipClearanceParameters(.5,1.)
        from blade_designer.geometry import span_extension
        original=span_extension.extend_tip_to_shroud
        def extend(g):
            if g.sections[0].m[0]>30:raise ValueError('Injected Splitter casing extension failure')
            return original(g)
        monkeypatch.setattr(span_extension,'extend_tip_to_shroud',extend)
    else:
        g=generate_impeller(p)
        if invalid=='missing':g.splitter_sections=None
        elif invalid=='span':g.splitter_sections[1].span=.6
        elif invalid=='collapsed':g.splitter_sections[-1].le.r[:]=g.splitter_sections[-1].le.r[0];g.splitter_sections[-1].le.theta_rad[:]=g.splitter_sections[-1].le.theta_rad[0];g.splitter_sections[-1].le.z[:]=g.splitter_sections[-1].le.z[0]
        elif invalid=='domain':
            p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
            for curve in (p.hub,p.shroud):
                for segment in curve.segments:segment.blade_row='row-1'
            g.splitter_sections[0].master_le.meridional_distance[:]=-100
        monkeypatch.setattr(tg,'generate_impeller',lambda _:g)
    for target in (case,tmp_path/'new'):
        with pytest.raises(ValueError):tg.export_turbogrid(target,p)
    assert {f.name:f.read_bytes() for f in case.iterdir()}==before
    assert not (tmp_path/'new').exists()


def test_main_only_bytes_match_pre_splitter_exporter(tmp_path):
    from test_stator_turbogrid_export import profiles
    from blade_designer.models.parameters import BladeParameters,BladeSection
    from test_tip_clearance import axial_parameters
    references=json.loads((Path(__file__).parent/'fixtures/turbogrid_main_only_sha256.json').read_text())
    for name in references['cases']:
        p=BladeParameters()
        if name=='middle':p.sections.insert(1,BladeSection(.5))
        elif name=='cw_x_cm':p.rotation_direction=RotationDirection.CW;p.turbogrid.rotation_axis='X';p.turbogrid.geometry_unit='CM'
        elif name=='clearance':p=axial_parameters();p.tip_clearance=TipClearanceParameters(.5,1.)
        actual={f.name:hashlib.sha256(f.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for f in tg.export_turbogrid(tmp_path/name,p)}
        archived=references['cases'][name]
        # Nose positioning intentionally changes profiles, not the archived
        # wall/initialization formats. Keep the historical hashes unchanged.
        for filename in actual:
            if filename!=p.turbogrid.profile_curve_filename:
                assert actual[filename]==archived[filename]
        assert actual[p.turbogrid.profile_curve_filename]!=archived[p.turbogrid.profile_curve_filename]
        geometry=generate_impeller(p)
        sections=geometry.sections
        if geometry.tip is not None:sections=[*sections,extend_tip_to_shroud(geometry)]
        parsed=profiles(tmp_path/name/p.turbogrid.profile_curve_filename)
        assert len(parsed)==len(sections)
        for (_,xyz,markers),section in zip(parsed,sections):
            expected,expected_markers=tg.closed_profile(section)
            expected=tg._external_xyz(expected,p.turbogrid)
            rounded=np.array([[float(f'{v:.{p.export.significant_digits}g}') for v in row] for row in expected])
            np.testing.assert_array_equal(xyz,rounded)
            assert markers==expected_markers
