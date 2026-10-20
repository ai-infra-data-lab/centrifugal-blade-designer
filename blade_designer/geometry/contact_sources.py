"""Snapshot identities and triangle-to-source parameter correspondence."""
import hashlib
import numpy as np
from .surface_envelope import _control_net
from .role_seams import ROLES


def _digest(arrays):
    digest=hashlib.sha256()
    for value in arrays:
        a=np.ascontiguousarray(value)
        digest.update(str((a.shape,a.dtype.str)).encode('ascii'));digest.update(a.tobytes())
    return digest.hexdigest()


def surface_fingerprint(surface):
    knots,degrees,net=_control_net(surface)
    return _digest([*knots,np.array(degrees),net])


def mapping_fingerprint(envelope):
    a=envelope['alignment'];m=envelope['mesh']
    return _digest([a['span_coordinates'],*[a['role_coordinates'][r] for r in ROLES],
                    m['vertices'],m['faces'],m['source_faces'],np.array(m['face_roles'],dtype='S2')])


def source_triangle_patch(envelope,face_id):
    """Map the recorded face order, rejecting modified mapping snapshots."""
    if type(face_id) is not int or face_id<0:raise ValueError('face_id must be a nonnegative integer.')
    try:
        mesh=envelope['mesh'];a=envelope['alignment']
        if mesh is None or face_id>=len(mesh['faces']):raise ValueError('face_id outside the recorded mesh.')
        if mapping_fingerprint(envelope)!=envelope.get('mapping_fingerprint'):
            raise ValueError('Missing or changed source mapping snapshot.')
        spans=np.asarray(a['span_coordinates']);offset=0
        for role in ROLES:
            xi=np.asarray(a['role_coordinates'][role]);count=2*(len(spans)-1)*(len(xi)-1)
            if offset<=face_id<offset+count:
                i,j=divmod((face_id-offset)//2,len(xi)-1)
                if mesh['face_roles'][face_id]!=role:raise ValueError('Role order does not match source mapping.')
                return {'source_face':face_id,'role':role,'span_range':spans[i:i+2].tolist(),
                        'xi_range':xi[j:j+2].tolist(),'diagonal_half':(face_id-offset)%2}
            offset+=count
    except (KeyError,TypeError,IndexError) as exc:
        raise ValueError('A recorded merged-role envelope with source mapping is required.') from exc
    raise ValueError('Face order does not match source parameter cells.')
