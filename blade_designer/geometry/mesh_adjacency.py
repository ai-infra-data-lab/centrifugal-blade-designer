"""Shared-edge diagnostics on already validated finite triangle meshes.

These float64 relations are not certified geometric predicates. A tolerance
band can mark near-coplanar neighbors as overlap candidates, not actual folds.
No welding, winding repair, vertex-link manifold test or CAD dependency.
"""
from collections import defaultdict
import numpy as np


def _edge_relation(vertices, first, second, tolerance):
    """Classify only two nondegenerate faces sharing exactly two vertex IDs."""
    shared=sorted(set(first) & set(second))
    start,end=vertices[shared]
    edge=end-start;length=np.linalg.norm(edge)
    if length<=tolerance:return 'UNRESOLVED'
    direction=edge/length
    third=[vertices[next(i for i in face if i not in shared)]-start for face in (first,second)]
    perpendicular=[v-np.dot(v,direction)*direction for v in third]
    heights=[np.linalg.norm(v) for v in perpendicular]
    if min(heights)<=tolerance:return 'UNRESOLVED'
    units=[v/h for v,h in zip(perpendicular,heights)]
    normals=[np.cross(direction,v) for v in units]
    distances=[abs(np.dot(perpendicular[0],normals[1])),abs(np.dot(perpendicular[1],normals[0]))]
    if max(distances)>tolerance:
        # Distinct planes meet along their common edge line. Each triangle
        # intersects that line only on the shared edge (real arithmetic).
        return 'EXPECTED_EDGE'
    return 'OVERLAP_CANDIDATE' if np.dot(*units)>0 else 'EXPECTED_EDGE'


def _nonmanifold_edges(faces, valid_ids, example_limit):
    """Count >2-face edge incidences; boundary edges are permitted."""
    incidence=defaultdict(list)
    for index in valid_ids:
        a,b,c=map(int,faces[index])
        for x,y in ((a,b),(b,c),(c,a)):
            incidence[tuple(sorted((x,y)))].append(int(index))
    bad=[(edge,ids) for edge,ids in incidence.items() if len(ids)>2]
    examples=[{'edge':list(edge),'face_count':len(ids),'face_examples':ids[:example_limit]}
              for edge,ids in bad[:example_limit]]
    return len(bad),examples
