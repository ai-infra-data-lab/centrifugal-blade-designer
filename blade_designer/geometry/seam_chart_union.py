"""Cover every pair of local chart domains; never infer a union from leaves alone."""
from copy import deepcopy
from itertools import combinations
import numpy as np
from .contact_sources import surface_fingerprint
from .mesh_contacts import _nonnegative,_positive_int
from .surface_envelope import _control_net,_insert
from .seam_injectivity import seam_projection_injectivity
from .seam_contact_refinement import subdivide_seam_neighborhood,local_seam_pair_injectivity


def _hull_points(surface,span,xi):
    """All active poles on a restricted rectangle, including internal knots."""
    knots,degrees,net=_control_net(surface);slices=[]
    for axis,(lo,hi) in enumerate((span,xi)):
        k=degrees[axis]
        knots[axis],net=_insert(knots[axis],net,k,axis,{x:k+1 if x in (0,1) else k for x in (lo,hi)})
        start=int(np.searchsorted(knots[axis],lo,side='right'))-1-k
        stop=int(np.searchsorted(knots[axis],hi,side='left'))
        slices.append(slice(start,stop))
    points=net[slices[0],slices[1]].reshape(-1,3)
    if not len(points) or not np.isfinite(points).all():raise ValueError('Finite nonempty source hull required.')
    return points


def _hull_separation(first,second,projections,clearance):
    axes=[*np.eye(3)]
    for projection in projections:
        if projection is not None:
            axis=np.asarray(projection)[0];norm=float(np.linalg.norm(axis))
            if not np.isfinite(norm) or norm<=0:raise ValueError('Projection axis must be finite and nonzero.')
            axes.append(axis/norm)
    axes=np.array(axes);origin=first[0]
    a=(first-origin)@axes.T;b=(second-origin)@axes.T
    gaps=np.maximum(b.min(axis=0)-a.max(axis=0),a.min(axis=0)-b.max(axis=0))
    index=int(np.argmax(gaps));lower=max(0.,float(gaps[index]))
    if not np.isfinite(gaps).all():raise ValueError('Hull separation must be finite.')
    return {'numeric_separated':bool(lower>clearance),'projection_lower_mm':lower,
            'axis':axes[index].tolist(),'required_lower_mm':float(clearance)}


def _check_union(sources,partition,*,nonadjacent_clearance_mm,collar_fraction,max_pairs):
    _nonnegative(nonadjacent_clearance_mm,'nonadjacent_clearance_mm');_positive_int(max_pairs,'max_pairs')
    _nonnegative(collar_fraction,'collar_fraction')
    if not 0<collar_fraction<1:raise ValueError('collar_fraction must be in (0,1).')
    root=partition['root_report']
    if [surface_fingerprint(s) for s in sources]!=partition['source_fingerprints']:
        raise ValueError('Source surface changed since local chart evaluation.')
    indices=sorted(partition['leaf_indices'],key=lambda i:partition['charts'][i]['report']['span_range'])
    leaves=[partition['charts'][i]['report'] for i in indices]
    required=len(leaves)*(len(leaves)-1)//2
    result={'partition_report':partition,'numeric_injective':False,'cross_chart_pairs_checked':False,
            'required_pairs':required,'max_pairs':max_pairs,'pair_records':[],'pair_scan_complete':False,
            'leaf_chart_indices':indices,'leaf_span_ranges':[r['span_range'] for r in leaves],
            'collar_fraction':float(collar_fraction),'nonadjacent_clearance_mm':float(nonadjacent_clearance_mm),
            'source_fingerprints':partition['source_fingerprints'],'coordinates_modified':False,
            'whole_geometry_verified':False,'continuous_surface_certified':False,'roundoff_certified':False}
    if root['numeric_injective']:
        return {**result,'status':root['status'],'reason':'root_chart','numeric_injective':True}
    if not partition['all_leaves_numeric_injective']:
        return {**result,'status':partition['status'],'reason':'leaf_conditions_unmet'}
    if required>max_pairs:return {**result,'status':'RESOURCE_LIMIT','reason':'max_pairs'}
    if (leaves[0]['span_range'][0]!=root['span_range'][0] or leaves[-1]['span_range'][1]!=root['span_range'][1]
            or any(a['span_range'][1]!=b['span_range'][0] for a,b in zip(leaves,leaves[1:]))):
        raise ValueError('Local chart leaves do not cover the requested Span interval.')
    ends=root['ends'];widths=root['widths'];cache={}

    def hull(bounds):
        key=tuple(bounds)
        if key not in cache:
            points=[]
            for source,end,width in zip(sources,ends,widths):
                xi=(0,width) if end==0 else (1-width,1)
                points.append(_hull_points(source,bounds,xi))
            cache[key]=np.concatenate(points)
        return cache[key]

    def separate(a,b,projections):
        return {'first_span_range':list(a),'second_span_range':list(b),
                **_hull_separation(hull(a),hull(b),projections,nonadjacent_clearance_mm)}

    records=[];limited=False
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            for i,j in combinations(range(len(leaves)),2):
                a,b=leaves[i],leaves[j];ar=a['span_range'];br=b['span_range']
                projections=[a['projection'],b['projection'],root['projection']]
                record={'first_leaf':i,'second_leaf':j,'numeric_compatible':False,'collar_report':None,'separations':[]}
                if j==i+1:
                    seam=ar[1];lo=seam-collar_fraction*(seam-ar[0]);hi=seam+collar_fraction*(br[1]-seam)
                    if not ar[0]<lo<seam<hi<br[1]:
                        records.append({**record,'reason':'collar_not_representable'});continue
                    collar=seam_projection_injectivity(sources[0],ends[0],sources[1],ends[1],
                        first_width=widths[0],second_width=widths[1],span_range=(lo,hi),
                        reference_min_mm=root['reference_min_mm'],monotonic_margin=root['monotonic_margin'],
                        refinements=root['refinements'],max_cells=root['max_cells'],projection_strategy=root['projection_strategy'])
                    record['collar_report']=collar;limited|=collar['status']=='RESOURCE_LIMIT'
                    if not collar['numeric_injective']:
                        records.append({**record,'reason':'collar_condition_unmet'});continue
                    projections.append(collar['projection'])
                    record['separations']=[separate((ar[0],lo),br,projections),separate(ar,(hi,br[1]),projections)]
                else:record['separations']=[separate(ar,br,projections)]
                record['numeric_compatible']=all(s['numeric_separated'] for s in record['separations'])
                records.append({**record,'reason':'covered' if record['numeric_compatible'] else 'hulls_not_separated'})
    except FloatingPointError as exc:raise ValueError('Non-finite chart-union arithmetic.') from exc
    complete=len(records)==required and not limited;met=complete and all(r['numeric_compatible'] for r in records)
    return {**result,'status':'NUMERIC_INJECTIVE_ON_CHART_UNION' if met else 'RESOURCE_LIMIT' if limited else 'UNRESOLVED',
            'reason':'all_domain_pairs_covered' if met else 'chart_pairs_unresolved','pair_records':records,
            'pair_scan_complete':complete,'cross_chart_pairs_checked':complete,'numeric_injective':met}


def seam_union_injectivity(first,first_end,second,second_end,*,first_width,second_width,
                           reference_min_mm,monotonic_margin,nonadjacent_clearance_mm,span_range=(0.,1.),
                           refinements=0,max_cells=4096,max_depth=4,max_charts=31,projection_strategy='average',
                           collar_fraction=.5,max_pairs=256):
    """Add complete domain-pair coverage to freshly computed local charts."""
    sources=[deepcopy(first),deepcopy(second)]
    partition=subdivide_seam_neighborhood(sources[0],first_end,sources[1],second_end,
        first_width=first_width,second_width=second_width,reference_min_mm=reference_min_mm,
        monotonic_margin=monotonic_margin,span_range=span_range,refinements=refinements,max_cells=max_cells,
        max_depth=max_depth,max_charts=max_charts,projection_strategy=projection_strategy)
    return _check_union(sources,partition,nonadjacent_clearance_mm=nonadjacent_clearance_mm,
                        collar_fraction=collar_fraction,max_pairs=max_pairs)


def local_seam_union_injectivity(surfaces,envelope,first_face,second_face,*,reference_min_mm,
                                 monotonic_margin,nonadjacent_clearance_mm,refinements=0,max_cells=4096,
                                 max_depth=4,max_charts=31,projection_strategy='average',collar_fraction=.5,max_pairs=256):
    """Opt-in union evidence for recorded source candidates; old report retained."""
    bound=local_seam_pair_injectivity(surfaces,envelope,first_face,second_face,
        reference_min_mm=reference_min_mm,monotonic_margin=monotonic_margin,refinements=refinements,
        max_cells=max_cells,max_depth=max_depth,max_charts=max_charts,projection_strategy=projection_strategy)
    sources=[deepcopy(surfaces[p['role']]) for p in bound['patches']]
    report=_check_union(sources,bound['neighborhood_report'],nonadjacent_clearance_mm=nonadjacent_clearance_mm,
                        collar_fraction=collar_fraction,max_pairs=max_pairs)
    return {'status':report['status'],'candidate_report':bound,'union_report':report,
            'expected_parameter_contact_only':report['numeric_injective'],'source_identity_checked':True,
            'mapping_identity_checked':True,'whole_geometry_verified':False,'continuous_surface_certified':False,'roundoff_certified':False}
