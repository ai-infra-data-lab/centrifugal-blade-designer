"""Float64 cone and vertex-link diagnostics; no welding or solid proof."""
from collections import defaultdict, Counter
import numpy as np


def _cone(vectors, tolerance):
    lengths=np.linalg.norm(vectors,axis=1)
    if min(lengths)<=tolerance:return None
    units=vectors/lengths[:,None]
    normal=np.cross(*units);sine=np.linalg.norm(normal)
    if sine==0 or min(lengths)*sine<=tolerance:return None
    return lengths,units,normal/sine,sine


def _ray_extent(direction, cone, tolerance):
    lengths,units,normal,sine=cone
    allowance=tolerance/min(lengths)
    if abs(np.dot(direction,normal))>allowance:return None
    a=np.dot(np.cross(direction,units[1]),normal)/sine
    b=np.dot(np.cross(units[0],direction),normal)/sine
    if min(a,b)<-allowance:return 0.
    denominator=max(a,0)/lengths[0]+max(b,0)/lengths[1]
    return 1/denominator if denominator>0 else None


def _vertex_relation(vertices, first, second, tolerance):
    """Two triangles with one shared ID: common cone rays beyond that vertex."""
    shared=next(iter(set(first)&set(second)))
    vectors=[vertices[[i for i in face if i!=shared]]-vertices[shared] for face in (first,second)]
    cones=[_cone(v,tolerance) for v in vectors]
    if any(c is None for c in cones):return 'UNRESOLVED'
    coplanar=max(np.max(np.abs(vectors[0]@cones[1][2])),np.max(np.abs(vectors[1]@cones[0][2])))<=tolerance
    if coplanar:
        normal=cones[0][2]
        projected=vectors[1]-(vectors[1]@normal)[:,None]*normal
        cones[1]=_cone(projected,tolerance)
        if cones[1] is None:return 'UNRESOLVED'
        directions=np.concatenate((cones[0][1],cones[1][1]))
    else:
        direction=np.cross(cones[0][2],cones[1][2]);length=np.linalg.norm(direction)
        if length==0:return 'UNRESOLVED'
        directions=[direction/length,-direction/length]
    unresolved=False
    for direction in directions:
        extents=[_ray_extent(direction,c,tolerance) for c in cones]
        if any(e==0 for e in extents):continue
        if any(e is None for e in extents):
            unresolved=True;continue
        if min(extents)>tolerance:return 'OVERLAP_CANDIDATE'
        unresolved=True
    return 'UNRESOLVED' if unresolved else 'EXPECTED_VERTEX'


def _vertex_links(faces, valid_ids, example_limit):
    """A boundary link is one simple path; an interior link one simple cycle."""
    links=defaultdict(list)
    for index in valid_ids:
        face=list(map(int,faces[index]))
        for position,vertex in enumerate(face):
            others=face[position+1:]+face[:position]
            links[vertex].append((tuple(sorted(others)),int(index)))
    count=0;examples=[]
    for vertex,entries in links.items():
        graph=defaultdict(set);degrees=Counter();edges=Counter(edge for edge,_ in entries)
        for (a,b),_ in entries:
            graph[a].add(b);graph[b].add(a);degrees.update((a,b))
        unseen=set(graph);components=0
        while unseen:
            components+=1;stack=[unseen.pop()]
            while stack:
                for neighbor in graph[stack.pop()] & unseen:
                    unseen.remove(neighbor);stack.append(neighbor)
        branches=[v for v,n in degrees.items() if n>2]
        duplicates=sum(n>1 for n in edges.values())
        if components!=1 or branches or duplicates or sum(n==1 for n in degrees.values()) not in (0,2):
            count+=1
            if len(examples)<example_limit:
                examples.append({'vertex':vertex,'link_nodes':len(graph),'link_edges':len(entries),
                                 'components':components,'branch_vertices':branches[:example_limit],
                                 'duplicate_link_edges':duplicates,'face_count':len(entries),
                                 'face_examples':[i for _,i in entries[:example_limit]]})
    return count,examples
