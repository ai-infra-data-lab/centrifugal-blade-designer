"""Validate adopted patch densities from an existing CAD result, without I/O."""
import re


def adopted_surface_counts(report, snapshot_hash, group):
    """Base blade patches only; no claims about fillets, STEP or full surfaces."""
    if group not in ('main','splitter'):raise ValueError('Unknown CAD blade set.')
    if not isinstance(report,dict):raise ValueError('実CADの完了結果がありません。先にCADを生成してください。')
    if not isinstance(snapshot_hash,str) or re.fullmatch(r'[0-9a-f]{64}',snapshot_hash) is None:
        raise ValueError('Invalid reference snapshot hash.')
    if report.get('parameter_snapshot_hash')!=snapshot_hash:
        raise ValueError('CAD結果と参照対象のsnapshotが異なります。現在の設計でCADを生成してください。')
    if report.get('geometry_type')!='impeller' or report.get('cad_unit')!='mm' or report.get('rotation_axis')!='Z':
        raise ValueError('CAD result requires Impeller / mm / Z axis.')
    if report.get('overall') not in ('PASS','WARNING') or report.get('cad_surface_status')!='PASS' or report.get('blade_solid_status')!='PASS':
        raise ValueError('翼面・翼solidの成功が確認できるCAD結果ではありません。')
    checks=report.get('checks')
    solids=checks.get('blade_solids') if isinstance(checks,dict) else None
    metrics=solids.get(group) if isinstance(solids,dict) else None
    if not isinstance(metrics,dict) or any(metrics.get(key) is not True for key in ('brep_valid','self_intersection_free','closed_shell')) or type(metrics.get('solid_count')) is not int or metrics['solid_count']!=1:
        raise ValueError('Selected blade set has no valid single closed BREP result.')
    counts=metrics.get('surface_grid_counts') if isinstance(metrics,dict) else None
    if not isinstance(counts,dict) or set(counts)!=set(('le','ps','te','ss')):
        raise ValueError('Selected CAD blade set has no complete role density record.')
    if any(type(n) is not int or n not in (33,65,129,257,513) for n in counts.values()):
        raise ValueError('Invalid adopted CAD surface grid count.')
    return dict(counts)
