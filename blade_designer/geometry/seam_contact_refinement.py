"""Source-bound seam neighborhoods; separate local charts never prove their union."""
from collections import Counter
from copy import deepcopy
from .contact_sources import source_triangle_patch,surface_fingerprint
from .mesh_contacts import _positive_int
from .role_seams import SEAMS
from .seam_injectivity import seam_projection_injectivity


def subdivide_seam_neighborhood(first,first_end,second,second_end,*,first_width,second_width,
                                reference_min_mm,monotonic_margin,span_range=(0.,1.),
                                refinements=0,max_cells=4096,max_depth=4,max_charts=31):
    """Bisect unresolved Span ranges, preserving the original widths and domain.

    A positive ROOT chart covers the whole requested neighborhood. Successful
    children with distinct projections are local evidence only: cross-chart
    pairs have not been checked. Limits retain unresolved leaves, never holes.
    max_cells is per chart; max_charts caps all chart evaluations including root.
    """
    _positive_int(max_charts,'max_charts')
    if type(max_depth) is not int or not 0<=max_depth<=8:raise ValueError('max_depth must be in [0,8].')
    sources=[deepcopy(first),deepcopy(second)]
    options=dict(first_width=first_width,second_width=second_width,reference_min_mm=reference_min_mm,
                 monotonic_margin=monotonic_margin,refinements=refinements,max_cells=max_cells)
    root=seam_projection_injectivity(sources[0],first_end,sources[1],second_end,span_range=span_range,**options)
    charts=[{'depth':0,'parent':None,'children':[],'report':root}];queue=[0];stops=Counter()
    while queue:
        index=queue.pop(0);node=charts[index];report=node['report']
        if report['numeric_injective']:continue
        reason=report['reason']
        if reason not in ('reference_rank','symmetric_bound_not_positive'):
            stops[reason]+=1;continue
        if node['depth']>=max_depth:stops['max_depth']+=1;continue
        if len(charts)+2>max_charts:stops['max_charts']+=1;continue
        lo,hi=report['span_range'];mid=lo+(hi-lo)/2
        if not lo<mid<hi:stops['span_not_bisectable']+=1;continue
        for bounds in ((lo,mid),(mid,hi)):
            child=seam_projection_injectivity(sources[0],first_end,sources[1],second_end,span_range=bounds,**options)
            child_index=len(charts);node['children'].append(child_index)
            charts.append({'depth':node['depth']+1,'parent':index,'children':[],'report':child})
            queue.append(child_index)
    leaves=[i for i,n in enumerate(charts) if not n['children']]
    all_local=all(charts[i]['report']['numeric_injective'] for i in leaves)
    limited=bool(stops['max_charts'] or any(n['report']['status']=='RESOURCE_LIMIT' for n in charts))
    status=(root['status'] if root['numeric_injective'] else 'RESOURCE_LIMIT' if limited
            else 'LOCAL_CHARTS_ONLY' if all_local else 'UNRESOLVED')
    return {'status':status,'root_report':root,'charts':charts,'leaf_indices':leaves,
            'chart_count':len(charts),'max_charts':max_charts,'max_depth':max_depth,
            'stop_reasons':dict(stops),'all_leaves_numeric_injective':all_local,
            'numeric_injective':root['numeric_injective'],'cross_chart_pairs_checked':False,
            'source_fingerprints':root['source_fingerprints'],'coordinates_modified':False,
            'whole_geometry_verified':False,'continuous_surface_certified':False,'roundoff_certified':False}


def local_seam_pair_injectivity(surfaces,envelope,first_face,second_face,*,reference_min_mm,
                                monotonic_margin,refinements=0,max_cells=4096,max_depth=4,max_charts=31):
    """Bind a declared cross-role shared-ID pair to its complete parent cells.

    The one root chart must cover both recorded cells before expected parameter
    contact can be reported. Subdivision does not shrink away a difficult part
    of either source triangle or rewrite the original contact/export report.
    """
    patches=[source_triangle_patch(envelope,i) for i in (first_face,second_face)]
    if first_face==second_face:raise ValueError('Distinct source triangles are required.')
    faces=envelope['mesh']['faces']
    if not set(faces[first_face])&set(faces[second_face]):raise ValueError('A shared-ID neighboring pair is required.')
    roles=[p['role'] for p in patches]
    seam=next((s for s in SEAMS if set((s[0],s[2]))==set(roles)),None)
    if seam is None:raise ValueError('A declared cross-role seam pair is required.')
    ordered=[next(p for p in patches if p['role']==role) for role in (seam[0],seam[2])]
    snapshots=[];widths=[]
    for patch,end in zip(ordered,(seam[1],seam[3])):
        role=patch['role']
        try:source=deepcopy(surfaces[role])
        except (KeyError,TypeError) as exc:raise ValueError('Selected source roles are required.') from exc
        if surface_fingerprint(source)!=envelope.get('source_fingerprints',{}).get(role):
            raise ValueError('Source surface changed or lacks a recorded identity.')
        bounds=patch['xi_range']
        if bounds[end]!=(0 if end==0 else 1):raise ValueError('Source cell does not touch its declared seam.')
        snapshots.append(source);widths.append(bounds[1]-bounds[0])
    span=[min(p['span_range'][0] for p in ordered),max(p['span_range'][1] for p in ordered)]
    report=subdivide_seam_neighborhood(snapshots[0],seam[1],snapshots[1],seam[3],
        first_width=widths[0],second_width=widths[1],span_range=span,
        reference_min_mm=reference_min_mm,monotonic_margin=monotonic_margin,refinements=refinements,
        max_cells=max_cells,max_depth=max_depth,max_charts=max_charts)
    return {'status':report['status'],'query_faces':[first_face,second_face],'patches':ordered,
            'seam':list(seam),'source_identity_checked':True,'mapping_identity_checked':True,
            'enclosing_parent_cells':True,'source_basis':'original_unmerged_splines',
            'expected_parameter_contact_only':report['numeric_injective'],'neighborhood_report':report,
            'whole_geometry_verified':False,'continuous_surface_certified':False,'roundoff_certified':False}
