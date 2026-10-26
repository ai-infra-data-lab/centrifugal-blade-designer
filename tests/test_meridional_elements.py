"""Independent definitions and analytic directed G0/G1 boundary constraints."""
from copy import deepcopy
from dataclasses import asdict
import json
import numpy as np
import pytest
from blade_designer.models.parameters import BladeParameters,BladeRow
from blade_designer.models.meridional import MeridionalCurveParameters,LineSegmentParameters
from blade_designer.models.blade_rows import initial_rows,row_parameters,validate_rows
from blade_designer.geometry.element_walls import generate_wall_element
from blade_designer.geometry.meridional_segments import generate_meridional
from blade_designer.fileio.project_io import save_project,load_project
from blade_designer.fileio.preview_job import snapshot_text


def test_owned_arc_outlet_controls_child_pose_and_preserves_blade_design():
    from blade_designer.models.meridional import ArcSegmentParameters
    p=project()
    for side,radius in (('hub',50),('shroud',60)):
        curve=MeridionalCurveParameters(0,radius,0,[LineSegmentParameters(10,'row-2'),
            ArcSegmentParameters(20,25,False,'row-1'),LineSegmentParameters(5,'row-2')])
        setattr(p,side,curve)
    p.blade_rows.append(duct('duct','row-1'))
    child=row_parameters(p,p.blade_rows[-1]);before=deepcopy(p.blade_rows[-1].parameters)
    for side in ('hub','shroud'):
        parent=generate_meridional(getattr(p,side)).segments[1]
        start=generate_meridional(getattr(child,side)).segments[0]
        np.testing.assert_allclose(start.start.zr,parent.end.zr,atol=1e-10)
        np.testing.assert_allclose(start.start_tangent,parent.end_tangent,atol=1e-12)
    p.hub.segments[1].sweep_deg=35
    updated=row_parameters(p,p.blade_rows[-1])
    assert updated.hub.start_angle_deg==pytest.approx(child.hub.start_angle_deg+10)
    assert p.blade_rows[-1].parameters==before


def test_wall_only_preview_process_has_no_blades_or_gui_dependencies(tmp_path):
    import subprocess
    import sys
    from blade_designer.fileio.preview_job import queue_preview,read_preview
    p=project();p.blade_rows=[duct('duct')];p.active_blade_row='duct'
    job=queue_preview(p,'meridional',True,tmp_path/'job')
    code='import sys; from blade_designer.fileio.preview_job import calculate_preview; calculate_preview(sys.argv[1]); assert not any(k.startswith(("PySide6","pyqtgraph","OCP")) for k in sys.modules)'
    result=subprocess.run([sys.executable,'-c',code,str(job)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    selected,rows=read_preview(job,p,'meridional',True)
    assert selected.selected_error is None
    assert selected.impeller is None and selected.diffuser is None and selected.legacy is None
    assert selected.meridional.sections==[] and len(rows.entries)==1
    assert rows.errors==[] and rows.entries[0][2].sections==[]
    assert len(rows.wall_chunks['hub'])==1


def test_blade_outputs_and_optimization_reject_wall_only_before_writing(tmp_path):
    from blade_designer.geometry.geometry_3d import generate_impeller,generate_diffuser_3d
    from blade_designer.fileio.turbogrid_export import export_turbogrid
    from blade_designer.fileio.export_readiness import assess_exports
    from blade_designer.optimization.coordinate_parameters import CoordinateStudy
    p=project();p.blade_rows.append(duct('duct'));p.active_blade_row='duct'
    for generator in (generate_impeller,generate_diffuser_3d):
        with pytest.raises(ValueError,match='no blade'):generator(p)
    target=tmp_path/'existing';target.mkdir();old=target/'hub.curve';old.write_bytes(b'original')
    with pytest.raises(ValueError,match='no profiles'):export_turbogrid(target,p)
    assert old.read_bytes()==b'original' and list(target.iterdir())==[old]
    assert all(route.status=='BLOCKED' for route in assess_exports(p).routes)
    with pytest.raises(ValueError,match='independent connected'):CoordinateStudy(p)


def test_crossing_private_walls_are_rejected():
    row=duct('duct')
    row.parameters.shroud=deepcopy(row.parameters.hub)
    with pytest.raises(ValueError,match='intersection or contact'):generate_wall_element(row.parameters)


def test_loading_wall_only_selection_keeps_distinct_stator_edges(tmp_path):
    from blade_designer.models.blade_rows import reconcile_visible_row_edges
    p=project();p.blade_rows[1].parameters.diffuser_edges.leading_edge.hub_m_flow_norm=.88
    p.blade_rows.append(duct('duct'));p.active_blade_row='duct'
    path=tmp_path/'different_edges.json';save_project(path,p)
    restored=reconcile_visible_row_edges(load_project(path))
    assert restored.blade_rows==p.blade_rows


def project():
    p=BladeParameters();p.blade_rows=initial_rows(p);p.active_blade_row='row-1'
    return p


def duct(identifier,upstream=None):
    p=BladeParameters()
    p.hub=MeridionalCurveParameters(100,100,20,[LineSegmentParameters(5,identifier)])
    p.shroud=MeridionalCurveParameters(100,110,20,[LineSegmentParameters(5,identifier)])
    return BladeRow(identifier,identifier,'meridional',p,True,upstream)


def test_independent_walls_do_not_overwrite_shared_or_other_elements():
    p=project();p.blade_rows+=[duct('duct-1'),duct('duct-2')];before=deepcopy(p)
    resolved=row_parameters(p,p.blade_rows[-1]);resolved.hub.segments[0].length=11
    assert p==before
    assert row_parameters(p,p.blade_rows[-1]).hub.start_z==100
    assert generate_wall_element(row_parameters(p,p.blade_rows[-1])).sections==[]


def test_two_level_connections_follow_both_parent_endpoints_and_tangents_without_mutation():
    p=project();p.blade_rows+=[duct('duct-1','row-1'),duct('duct-2','duct-1')]
    before=deepcopy(p);validate_rows(p)
    for parent_id,child_id in (('row-1','duct-1'),('duct-1','duct-2')):
        parent=next(row for row in p.blade_rows if row.identifier==parent_id)
        child=next(row for row in p.blade_rows if row.identifier==child_id)
        a=row_parameters(p,parent);b=row_parameters(p,child)
        for side in ('hub','shroud'):
            end=generate_meridional(getattr(a,side)).segments[-1]
            start=generate_meridional(getattr(b,side)).segments[0]
            np.testing.assert_allclose(start.start.zr,end.end.zr,atol=1e-10,rtol=0)
            np.testing.assert_allclose(start.start_tangent,end.end_tangent,atol=1e-12,rtol=0)
    assert p==before
    old=row_parameters(p,p.blade_rows[-1]).hub.start_z
    p.hub.start_z+=7
    assert row_parameters(p,p.blade_rows[-1]).hub.start_z==pytest.approx(old+7)
    assert p.blade_rows[-1].parameters.hub==before.blade_rows[-1].parameters.hub


@pytest.mark.parametrize('problem',['cycle','missing','flag','shared_connection','nonindependent_duct'])
def test_invalid_connection_graph_is_rejected(problem):
    p=project();p.blade_rows+=[duct('duct-1','row-1')]
    if problem=='cycle':p.blade_rows[-1].upstream_row='duct-1'
    elif problem=='missing':p.blade_rows[-1].upstream_row='absent'
    elif problem=='flag':p.blade_rows[-1].independent_meridional=1
    elif problem=='shared_connection':p.blade_rows[0].upstream_row='duct-1'
    else:p.blade_rows[-1].independent_meridional=False
    with pytest.raises(ValueError):validate_rows(p)


def test_old_snapshot_bytes_preserved_and_explicit_connections_roundtrip(tmp_path):
    p=project();old=asdict(p)
    for row in old['blade_rows']:
        row.pop('independent_meridional');row.pop('upstream_row')
        # The older boundary-option compatibility is already part of snapshot_text.
        row['parameters']['cad_export'].pop('sector_boundary')
    old['cad_export'].pop('sector_boundary')
    expected=json.dumps({'schema_version':'0.4',**old},allow_nan=False,sort_keys=True,
                        default=lambda v:v.value if hasattr(v,'value') else v.item())
    assert snapshot_text(p)==expected
    path=tmp_path/'project.json';save_project(path,p)
    assert 'independent_meridional' not in path.read_text(encoding='utf-8')
    p.blade_rows.append(duct('duct-1','row-1'));p.active_blade_row='duct-1'
    save_project(path,p);assert load_project(path)==p
    before=path.read_bytes();p.blade_rows[-1].upstream_row='duct-1'
    with pytest.raises(ValueError):save_project(path,p)
    assert path.read_bytes()==before
