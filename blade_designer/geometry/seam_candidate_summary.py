"""Bounded inventory of cross-role shared-ID pairs, with separate evidence.

This is neither an all-surface contact scan nor an export acceptance gate.
"""
from collections import Counter
from copy import deepcopy
from itertools import combinations
import numpy as np
from .boundary_gap import boundary_gap_envelope
from .boundary_identity import boundary_curve_identity
from .contact_sources import mapping_fingerprint, source_triangle_patch, surface_fingerprint
from .mesh_contacts import _mesh, _nonnegative, _positive_int
from .role_seams import ROLES, SEAMS
from .seam_chart_union import local_seam_union_injectivity


def seam_candidate_summary(surfaces, envelope, *, gap_tolerance_mm,
                           reference_min_mm, monotonic_margin, nonadjacent_clearance_mm,
                           max_pair_visits=100000, max_candidates=4096, max_evaluated=64,
                           max_triangles=20000):
    """Inventory shared vertices, then diagnose a deterministic bounded prefix.

    Counts refer only to discovered unique cross-role face pairs. An interrupted
    inventory is never advertised as a total; unexamined records remain explicit.
    No tolerance-based merging or acceptance of mismatched source curves occurs.
    """
    for value, name in ((max_pair_visits,'max_pair_visits'),(max_candidates,'max_candidates'),
                        (max_evaluated,'max_evaluated'),(max_triangles,'max_triangles')):
        _positive_int(value,name)
    for value,name in ((gap_tolerance_mm,'gap_tolerance_mm'),(reference_min_mm,'reference_min_mm'),
                       (monotonic_margin,'monotonic_margin'),(nonadjacent_clearance_mm,'nonadjacent_clearance_mm')):
        _nonnegative(value,name)
    sources=deepcopy(surfaces); snapshot=deepcopy(envelope)
    if set(sources)!=set(ROLES):raise ValueError('All four role surfaces required.')
    fingerprints={r:surface_fingerprint(sources[r]) for r in ROLES}
    if fingerprints!=snapshot.get('source_fingerprints'):raise ValueError('Changed source snapshot.')
    if mapping_fingerprint(snapshot)!=snapshot.get('mapping_fingerprint'):
        raise ValueError('Missing or changed source mapping snapshot.')
    mesh=snapshot['mesh'];_,faces=_mesh(mesh['vertices'],mesh['faces'],max_triangles)
    roles=mesh['face_roles']
    if len(roles)!=len(faces) or any(r not in ROLES for r in roles):
        raise ValueError('Invalid face roles.')
    incidence={}
    for face, vertices in enumerate(faces):
        for vertex in set(map(int,vertices)):incidence.setdefault(vertex,[]).append(face)
    pairs=set();visits=0;stop=None
    for vertex in sorted(incidence):
        for a,b in combinations(incidence[vertex],2):
            if visits==max_pair_visits:stop='max_pair_visits';break
            visits+=1
            if roles[a]==roles[b] or (a,b) in pairs:continue
            if len(pairs)==max_candidates:stop='max_candidates';break
            pairs.add((a,b))
        if stop:break
    records=[];patches={};cache={}
    for index,(a,b) in enumerate(sorted(pairs)):
        record={'faces':[a,b],'roles':[roles[a],roles[b]],'status':'UNEXAMINED',
                'identity_report':None,'gap_report':None,'chart_report':None,
                'expected_parameter_contact_only':False}
        if index>=max_evaluated:
            records.append(record);continue
        for face in (a,b):
            if face not in patches:patches[face]=source_triangle_patch(snapshot,face)
        pa,pb=patches[a],patches[b]
        seam=next((s for s in SEAMS if {s[0],s[2]}=={roles[a],roles[b]}),None)
        if seam is None:
            records.append({**record,'status':'UNDECLARED_ROLE_PAIR'});continue
        r,e,t,f=seam
        first,second=(pa,pb) if pa['role']==r else (pb,pa)
        if first['xi_range'][e]!=float(e==-1) or second['xi_range'][f]!=float(f==-1):
            records.append({**record,'status':'OUTSIDE_DECLARED_BOUNDARY'});continue
        span=(min(first['span_range'][0],second['span_range'][0]),
              max(first['span_range'][1],second['span_range'][1]))
        key=(*seam,*span)
        if key not in cache:
            cache[key]=(boundary_curve_identity(sources[r],e,sources[t],f,span_range=span),
                        boundary_gap_envelope(sources[r],e,sources[t],f,span_range=span,
                                              gap_tolerance_mm=gap_tolerance_mm))
        identity,gap=cache[key]
        chart=local_seam_union_injectivity(sources,snapshot,a,b,
            reference_min_mm=reference_min_mm,monotonic_margin=monotonic_margin,
            nonadjacent_clearance_mm=nonadjacent_clearance_mm)
        met=chart['expected_parameter_contact_only']
        records.append({**record,'status':'EXPECTED_PARAMETER_CONTACT_ONLY' if met else 'UNRESOLVED',
                        'identity_report':deepcopy(identity),'gap_report':deepcopy(gap),
                        'chart_report':chart,'expected_parameter_contact_only':met})
    counts=dict(Counter(r['status'] for r in records))
    return {'status':'RESOURCE_LIMIT' if stop or counts.get('UNEXAMINED',0) else 'DIAGNOSTICS_RECORDED',
            'inventory_complete':stop is None,'inventory_stop_reason':stop,
            'candidate_count_is_total':stop is None,'discovered_candidates':len(pairs),
            'pair_visits':visits,'max_pair_visits':max_pair_visits,'max_candidates':max_candidates,
            'max_evaluated':max_evaluated,'records':records,'counts':counts,
            'evaluation_complete':not bool(counts.get('UNEXAMINED',0)),
            'source_fingerprints':fingerprints,'mapping_fingerprint':snapshot['mapping_fingerprint'],
            'source_identity_checked':True,'mapping_identity_checked':True,
            'coordinates_modified':False,'physical_gap_certified':False,'roundoff_certified':False,
            'continuous_surface_certified':False,'whole_geometry_verified':False,
            'export_ready':False,'scope':'cross_role_shared_vertex_ids_only'}
