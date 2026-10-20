"""Error-aware self screening with explicit unresolved source neighborhoods.

Position bounds alone cannot establish local source injectivity at shared IDs.
Expected triangle joins with nonzero error remain uncertain, never excluded.
"""
import numpy as np
from .error_aware_contacts import _errors,_separation_lower
from .mesh_contacts import _mesh,_nonnegative,_positive_int,_tree,_pairs
from .mesh_adjacency import _edge_relation,_nonmanifold_edges
from .mesh_vertex_adjacency import _vertex_relation,_vertex_links


def error_aware_self_contacts(vertices,faces,error_upper_mm,*,clearance_mm,
                              adjacency_tolerance_mm,area_epsilon_mm2,
                              max_work=500000,max_examples=100,max_triangles=20000):
    """Inspect every distinct face pair conservatively using expanded AABBs.

    Clearance applies to nonlocal pairs only; shared edge/vertex contact is
    expected topology. Zero-error expected joins are accepted numerically;
    positive source error leaves local injectivity unresolved. No welding,
    topology repair, source refinement or output gate is performed.
    max_examples truncates examples only, never counts or the scan.
    """
    for value,name in ((clearance_mm,'clearance_mm'),(adjacency_tolerance_mm,'adjacency_tolerance_mm'),
                       (area_epsilon_mm2,'area_epsilon_mm2')):_nonnegative(value,name)
    for value,name in ((max_work,'max_work'),(max_examples,'max_examples'),(max_triangles,'max_triangles')):
        _positive_int(value,name)
    v,f=_mesh(vertices,faces,max_triangles)
    stats={'work_units':0,'node_pair_tests':0,'triangle_pair_tests':0,'stop_reason':None}
    counts={key:0 for key in ('expected_edge_pairs','expected_vertex_pairs','local_error_uncertain_pairs',
                             'local_relation_unresolved_pairs','local_contact_candidates',
                             'nonlocal_contact_candidates','nonlocal_uncertain_pairs','nonlocal_separated_pairs')}
    examples=[];nonlocal_examples=[];issues=0

    def record(i,j,kind,budget,lower=None):
        nonlocal issues
        issues+=1
        example={'first_face':i,'second_face':j,'kind':kind,
                 'error_sum_mm':float(budget),'projection_lower_mm':lower}
        if len(examples)<max_examples:examples.append(example)
        if kind.startswith('NONLOCAL_') and len(nonlocal_examples)<max_examples:
            nonlocal_examples.append(example.copy())

    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            errors=_errors(error_upper_mm,len(f));triangles=v[f]
            area=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)/2
            if not np.isfinite(area).all():raise ValueError('Triangle areas must be finite.')
            degenerate=np.flatnonzero(area<=area_epsilon_mm2);valid=np.flatnonzero(area>area_epsilon_mm2)
            edge_count,edge_examples=_nonmanifold_edges(f,valid,max_examples)
            vertex_count,vertex_examples=_vertex_links(f,valid,max_examples)
            margin=(errors+clearance_mm/2)[:,None]
            lows=triangles.min(axis=1)-margin;highs=triangles.max(axis=1)+margin
            if len(valid):
                tree=_tree(lows,highs,valid)
                for i,j in _pairs(tree,tree,True,0.,max_work,stats):
                    shared=len(set(f[i])&set(f[j]));budget=float(errors[i]+errors[j])
                    if not np.isfinite(budget):raise ValueError('Error sum must be finite.')
                    if shared:
                        relation=(_edge_relation(v,f[i],f[j],adjacency_tolerance_mm) if shared==2 else
                                  _vertex_relation(v,f[i],f[j],adjacency_tolerance_mm) if shared==1 else
                                  'OVERLAP_CANDIDATE')
                        if relation.startswith('EXPECTED_'):
                            counts['expected_edge_pairs' if shared==2 else 'expected_vertex_pairs']+=1
                            if budget>0:
                                counts['local_error_uncertain_pairs']+=1
                                record(i,j,'LOCAL_SOURCE_UNCERTAIN',budget)
                        elif relation=='UNRESOLVED':
                            counts['local_relation_unresolved_pairs']+=1
                            record(i,j,'LOCAL_RELATION_UNRESOLVED',budget)
                        else:
                            counts['local_contact_candidates']+=1
                            record(i,j,'LOCAL_TRIANGLE_CONTACT_CANDIDATE',budget)
                        continue
                    lower=_separation_lower(triangles[i],triangles[j])
                    required=budget+clearance_mm
                    if not np.isfinite(lower+required):raise ValueError('Separation arithmetic must be finite.')
                    if lower>required:
                        counts['nonlocal_separated_pairs']+=1
                    else:
                        contact=lower==0
                        counts['nonlocal_contact_candidates' if contact else 'nonlocal_uncertain_pairs']+=1
                        record(i,j,'NONLOCAL_TRIANGLE_CONTACT_CANDIDATE' if contact else 'NONLOCAL_UNCERTAIN',budget,lower)
    except FloatingPointError as exc:
        raise ValueError('Non-finite arithmetic in error-aware self screening.') from exc
    pairs_complete=stats['stop_reason'] is None and not len(degenerate)
    complete=pairs_complete and not (edge_count or vertex_count or counts['local_relation_unresolved_pairs'])
    contacts=counts['local_contact_candidates']+counts['nonlocal_contact_candidates']
    uncertain=counts['local_error_uncertain_pairs']+counts['nonlocal_uncertain_pairs']
    status=('CONTACT_CANDIDATES_FOUND' if contacts else 'INCOMPLETE' if not complete else
            'UNCERTAIN' if uncertain else 'NUMERIC_NO_UNEXPECTED_CONTACT')
    return {'status':status,'scan_complete':bool(complete),'pair_scan_complete':bool(pairs_complete),
            'numeric_no_unexpected_contact':bool(complete and not contacts and not uncertain),
            'nonlocal_numeric_separated':bool(pairs_complete and not counts['nonlocal_contact_candidates']
                                              and not counts['nonlocal_uncertain_pairs']),
            **counts,**stats,'triangles':len(f),'degenerate_faces':degenerate.tolist(),
            'nonmanifold_edge_count':edge_count,'nonmanifold_edge_examples':edge_examples,
            'nonmanifold_vertex_count':vertex_count,'nonmanifold_vertex_examples':vertex_examples,
            'issue_pairs':issues,'examples':examples,'examples_truncated':issues>len(examples),
            'nonlocal_examples':nonlocal_examples,
            'nonlocal_examples_truncated':counts['nonlocal_contact_candidates']+counts['nonlocal_uncertain_pairs']>len(nonlocal_examples),
            'clearance_mm':float(clearance_mm),'adjacency_tolerance_mm':float(adjacency_tolerance_mm),
            'area_epsilon_mm2':float(area_epsilon_mm2),'error_bounds_assumed_valid':True,
            'roundoff_certified':False,'continuous_surface_certified':False,
            'containment_checked':False,'whole_geometry_verified':False}
