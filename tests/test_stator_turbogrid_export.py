"""Selected stator exports: analytic placement, ownership and historical compatibility."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from blade_designer.fileio.project_io import load_project, save_project
from blade_designer.fileio.turbogrid_export import export_turbogrid
from blade_designer.geometry.geometry_3d import generate_diffuser_3d
from blade_designer.geometry.row_domain import preview_wall_chunks
from blade_designer.models.blade_rows import initial_rows, row_parameters, row_snapshot
from blade_designer.models.meridional import MeridionalCurveParameters, LineSegmentParameters
from blade_designer.models.parameters import (BladeParameters, BladeRow, BladeSection,
    BladeAngleParameters, DistributionPoint, EdgeType, RotationDirection)


def stator_project(identifier="row-2"):
    p=BladeParameters()
    p.hub=MeridionalCurveParameters(10,50,30,[LineSegmentParameters(100) for _ in range(4)])
    p.shroud=MeridionalCurveParameters(15,65,30,[LineSegmentParameters(100) for _ in range(4)])
    for wall in (p.hub,p.shroud):
        for i,segment in enumerate(wall.segments):
            segment.blade_row="row-1" if i==0 else "row-3" if i==3 else "row-2"
    for side in ("hub","shroud"):
        setattr(p.diffuser_edges.leading_edge,side+"_m_flow_norm",.35)
        setattr(p.diffuser_edges.trailing_edge,side+"_m_flow_norm",.6)
    p.diffuser_profile.blade_angle=BladeAngleParameters([DistributionPoint(0,20),DistributionPoint(1,20)])
    p.export.significant_digits=15
    p.blade_rows=initial_rows(p)
    p.blade_rows[1].parameters.geometry.vane_count=17
    rc=row_snapshot(p)
    rc.geometry.vane_count=11
    rc.geometry.theta_le_deg=25
    for side in ("hub","shroud"):
        setattr(rc.diffuser_edges.leading_edge,side+"_m_flow_norm",.8)
        setattr(rc.diffuser_edges.trailing_edge,side+"_m_flow_norm",.9)
    p.blade_rows.append(BladeRow("row-3","RC","diffuser",rc))
    p.active_blade_row=identifier
    return p


def profiles(path):
    result=[]
    for line in path.read_text().splitlines():
        if line.startswith('#'):result.append((line,[],{}))
        else:
            fields=line.split();result[-1][1].append([float(v) for v in fields[:3]])
            if len(fields)==4:result[-1][2][len(result[-1][1])-1]=fields[3]
    return [(label,np.array(xyz),markers) for label,xyz,markers in result]


@pytest.mark.parametrize('identifier',['row-2','row-3'])
@pytest.mark.parametrize('direction',list(RotationDirection))
def test_selected_stator_profiles_walls_and_independent_settings(tmp_path,identifier,direction):
    p=stator_project(identifier)
    selected=next(r for r in p.blade_rows if r.identifier==identifier)
    selected.parameters.rotation_direction=direction
    # A stale top-level count and edge setting must not replace the selected snapshot.
    p.geometry.vane_count=99
    for s in selected.parameters.sections:s.edge_parameters.te_type=EdgeType.CUTOFF
    before=deepcopy(p);resolved=row_parameters(p,selected)
    g=generate_diffuser_3d(resolved)
    files=export_turbogrid(tmp_path,p)
    assert p==before
    actual=profiles(files[2])
    assert [label for label,_,_ in actual]==['# Hub','# Tip']
    assert [s.span for s in g.sections]==[0,1]
    for (label,xyz,markers),s in zip(actual,g.sections):
        expected=np.concatenate([s.le.xyz[:-1],s.ps.xyz[:-1],s.te.xyz[:-1],s.ss.xyz[::-1][:-1],s.le.xyz[:1]])
        np.testing.assert_allclose(xyz,expected,atol=1e-12)
        np.testing.assert_array_equal(xyz[0],xyz[-1])
        assert np.all(np.linalg.norm(np.diff(xyz,axis=0),axis=1)>0)
        assert sorted(markers.values())==['le','te']
        for name,edge in (('le',s.le),('te',s.te)):
            marked=xyz[next(i for i,value in markers.items() if value==name)]
            np.testing.assert_allclose(marked,edge.xyz[min(len(edge.r)//2,len(edge.r)-2)],atol=1e-12)
        # Every output point is on the analytic cone, including resampled edges.
        radius=np.hypot(xyz[:,0],xyz[:,1])
        np.testing.assert_allclose(radius,50+15*s.span+(xyz[:,2]-10-5*s.span)*np.tan(np.pi/6),atol=1e-12)
    chunks=preview_wall_chunks(p,g,identifier)
    start,end=(100,300) if identifier=='row-2' else (300,400)
    for side,path,span in zip(('hub','shroud'),files[:2],(0,1)):
        wall=np.loadtxt(path)
        distances=np.linspace(start,end,getattr(p,side).export_points)
        expected=np.column_stack((50+15*span+distances*.5,np.zeros(len(distances)),10+5*span+distances*np.cos(np.pi/6)))
        np.testing.assert_allclose(wall,expected,atol=1e-12)
        chunk=chunks[side][0]
        np.testing.assert_allclose(wall[[0,-1]],np.column_stack((chunk.r[[0,-1]],np.zeros(2),chunk.z[[0,-1]])),atol=1e-12)
    inf=files[3].read_text()
    assert f'Number of Blade Sets: {selected.parameters.geometry.vane_count}' in inf
    assert 'Number of Blades Per Set: 1' in inf
    assert 'Blade 0 TE: EllipseEnd' in inf  # independent of hidden Impeller settings


@pytest.mark.parametrize('axis,order',[('Z',[0,1,2]),('X',[2,0,1]),('Y',[1,2,0])])
@pytest.mark.parametrize('unit,scale',[('MM',1),('CM',.1),('M',.001)])
def test_static_units_axis_and_roundtrip(tmp_path,axis,order,unit,scale):
    p=stator_project();q=p.blade_rows[1].parameters
    q.turbogrid.rotation_axis=axis;q.turbogrid.geometry_unit=unit
    json_path=tmp_path/'project.json';save_project(json_path,p)
    restored=load_project(json_path)
    files=export_turbogrid(tmp_path/'actual',restored)
    q.turbogrid.rotation_axis='Z';q.turbogrid.geometry_unit='MM'
    reference=export_turbogrid(tmp_path/'reference',p)
    for actual_path,base_path in zip(files[:2],reference[:2]):
        np.testing.assert_allclose(np.loadtxt(actual_path),np.loadtxt(base_path)[:,order]*scale,atol=1e-12)
    for (_,actual,_),(_,base,_) in zip(profiles(files[2]),profiles(reference[2])):
        np.testing.assert_allclose(actual,base[:,order]*scale,atol=1e-12)
    assert f'Geometry Units: {unit}' in files[3].read_text()
    assert f'Axis of Rotation: {axis}' in files[3].read_text()


def test_stator_cutoff_uses_static_end_type_and_legacy_unassigned_walls(tmp_path):
    p=stator_project()
    p.blade_rows[1].parameters.diffuser_profile.edge_parameters.te_type=EdgeType.CUTOFF
    for wall in (p.hub,p.shroud):
        for segment in wall.segments:segment.blade_row=None
    files=export_turbogrid(tmp_path,p)
    assert 'Blade 0 TE: CutOffEnd' in files[3].read_text()
    np.testing.assert_allclose(np.loadtxt(files[0])[[0,-1],0],[50,250],atol=1e-12)


@pytest.mark.parametrize('invalid',['missing_wall','disconnected','outside_le','outside_profile',
    'edges','wall','nan','filename','precision','unknown_row','no_active'])
def test_static_invalid_input_preserves_existing_output(tmp_path,invalid):
    p=stator_project();case=tmp_path/'case';files=export_turbogrid(case,p)
    before={f.name:f.read_bytes() for f in files}
    q=p.blade_rows[1].parameters
    if invalid=='missing_wall':
        for segment in p.shroud.segments:segment.blade_row='row-1'
    elif invalid=='disconnected':
        p.hub.segments[2].blade_row='row-1';p.hub.segments[3].blade_row='row-2'
    elif invalid=='outside_le':q.diffuser_edges.leading_edge.hub_m_flow_norm=.2
    elif invalid=='outside_profile':q.diffuser_edges.leading_edge.hub_m_flow_norm=.25
    elif invalid=='edges':q.diffuser_edges.trailing_edge.hub_m_flow_norm=.1
    elif invalid=='wall':p.hub.segments[0].length=-1
    elif invalid=='nan':q.diffuser_profile.thickness.points[0].value=float('nan')
    elif invalid=='filename':q.turbogrid.hub_curve_filename='../escape.curve'
    elif invalid=='precision':q.export.significant_digits=1
    elif invalid=='unknown_row':p.hub.segments[0].blade_row='missing'
    else:p.active_blade_row=None
    with pytest.raises(ValueError):export_turbogrid(case,p)
    assert {f.name:f.read_bytes() for f in files}==before
    assert sorted(f.name for f in case.iterdir())==sorted(before)
    with pytest.raises(ValueError):export_turbogrid(tmp_path/'new',p)
    assert not (tmp_path/'new').exists()


@pytest.mark.parametrize('case',['legacy','middle_span','cutoff_x_cm'])
def test_impeller_output_matches_prechange_ascii_reference(tmp_path,case):
    # Historical compatibility reference, captured before changing exporter code.
    p=BladeParameters()
    if case=='middle_span':p.sections.insert(1,BladeSection(.5))
    if case=='cutoff_x_cm':
        for s in p.sections:s.edge_parameters.te_type=EdgeType.CUTOFF
        p.turbogrid.rotation_axis='X';p.turbogrid.geometry_unit='CM'
    reference=json.loads((Path(__file__).parent/'fixtures/turbogrid_impeller_sha256.json').read_text())
    actual={f.name:hashlib.sha256(f.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            for f in export_turbogrid(tmp_path,p)}
    assert actual==reference['cases'][case]
