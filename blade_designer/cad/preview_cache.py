"""Optional local numeric cache; preview.json remains the compatibility source."""
from pathlib import Path
import hashlib,json,math,re,zipfile
from numbers import Real
import numpy as np

_MAX_BYTES=512*1024*1024
_GROUPS=('triangles','triangles_single','triangles_full')


def _points(rows,shape):
    array=np.asarray(rows,dtype=np.float64)
    if array.size==0:array=array.reshape((0,*shape))
    if array.ndim!=len(shape)+1 or array.shape[1:]!=shape or not np.isfinite(array).all():
        raise ValueError('Invalid CAD preview coordinates.')
    return array


def _validate_payload(data):
    if not isinstance(data,dict):raise ValueError('Invalid CAD preview payload.')
    radius=data.get('fillet_radius_mm');count=data.get('blade_count')
    if (data.get('scope') not in ('disk_only','blade_only','blade_hub','periodic_sector','full_impeller') or
            not isinstance(data.get('snapshot_hash'),str) or not data['snapshot_hash'] or
            type(count) is not int or count<1 or not isinstance(radius,Real) or isinstance(radius,bool) or
            not math.isfinite(radius) or radius<0):
        raise ValueError('Invalid CAD preview identity or settings.')
    if 'triangles' not in data:raise ValueError('Missing CAD preview triangles.')
    for group in _GROUPS:
        if group not in data:continue
        roles=data[group]
        if not isinstance(roles,dict) or any(not isinstance(role,str) for role in roles):
            raise ValueError('Invalid CAD preview roles.')
        for rows in roles.values():_points(rows,(3,3))
    if not isinstance(data.get('edges',[]),(list,tuple)):raise ValueError('Invalid CAD preview edges.')
    for rows in data.get('edges',[]):_points(rows,(3,))


def write_preview_cache(data,job):
    _validate_payload(data)
    job=Path(job);source=job/'preview.json';stat=source.stat();arrays={};known={};refs={}
    for group in _GROUPS:
        if group not in data:continue
        if not isinstance(data[group],dict):raise ValueError('Invalid CAD preview groups.')
        refs[group]={}
        for role,rows in data[group].items():
            if not isinstance(role,str):raise ValueError('Invalid CAD preview role.')
            array=_points(rows,(3,3));digest=(array.shape,hashlib.sha256(array.tobytes()).digest())
            key=known.get(digest)
            if key is None:key='a'+str(len(known));known[digest]=key;arrays[key]=array
            refs[group][role]=key
    if 'triangles' not in refs:raise ValueError('Missing CAD preview triangles.')
    edges=[_points(row,(3,)) for row in data.get('edges',[])]
    arrays['edge_points']=np.concatenate(edges) if edges else np.empty((0,3),dtype=np.float64)
    arrays['edge_offsets']=np.cumsum([0]+[len(row) for row in edges],dtype=np.int64)
    metadata={'version':1,'source_stamp':[stat.st_size,stat.st_mtime_ns],
        'payload':{key:value for key,value in data.items() if key not in (*_GROUPS,'edges')},'refs':refs}
    arrays['meta']=np.frombuffer(json.dumps(metadata,ensure_ascii=False,allow_nan=False).encode('utf-8'),dtype=np.uint8)
    if sum(value.nbytes for value in arrays.values())>_MAX_BYTES:raise ValueError('CAD preview cache exceeds the limit.')
    temporary=job/'preview.cache.part.npz';np.savez_compressed(temporary,**arrays)
    temporary.replace(job/'preview.cache.npz')


def _read_arrays(path):
    arrays={}
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist();names=[entry.filename for entry in entries]
        if len(names)!=len(set(names)) or sum(e.file_size for e in entries)>_MAX_BYTES:
            raise ValueError('Invalid CAD preview cache size or duplicate arrays.')
        for entry in entries:
            name=entry.filename
            if not re.fullmatch(r'(meta|edge_points|edge_offsets|a[0-9]+)\.npy',name):
                raise ValueError('Unexpected CAD preview cache member.')
            with archive.open(entry) as stream:
                version=np.lib.format.read_magic(stream)
                reader={ (1,0):np.lib.format.read_array_header_1_0,(2,0):np.lib.format.read_array_header_2_0}.get(version)
                if reader is None:raise ValueError('Unsupported CAD preview array version.')
                shape,_,dtype=reader(stream)
                if dtype.hasobject or stream.tell()+math.prod(shape)*dtype.itemsize!=entry.file_size:
                    raise ValueError('Invalid CAD preview array length or object dtype.')
                key=name[:-4]
                valid=(dtype==np.uint8 and len(shape)==1 and shape[0]<=1024*1024 if key=='meta' else
                    dtype==np.int64 and len(shape)==1 and shape[0]>=1 if key=='edge_offsets' else
                    dtype==np.float64 and len(shape)==2 and shape[1:]==(3,) if key=='edge_points' else
                    dtype==np.float64 and len(shape)==3 and shape[1:]==(3,3))
                if not valid:raise ValueError('Invalid CAD preview array shape or dtype.')
            with archive.open(entry) as stream:arrays[key]=np.lib.format.read_array(stream,allow_pickle=False)
    return arrays


def read_preview_cache(job):
    job=Path(job);stat=(job/'preview.json').stat();arrays=_read_arrays(job/'preview.cache.npz')
    if not {'meta','edge_points','edge_offsets'}<=arrays.keys():raise ValueError('Incomplete CAD preview cache.')
    metadata=json.loads(arrays.pop('meta').tobytes().decode('utf-8'))
    if (not isinstance(metadata,dict) or type(metadata.get('version')) is not int or metadata['version']!=1 or
            metadata.get('source_stamp')!=[stat.st_size,stat.st_mtime_ns]):
        raise ValueError('Stale or unsupported CAD preview cache.')
    payload=metadata.get('payload');refs=metadata.get('refs')
    if not isinstance(payload,dict) or not isinstance(refs,dict) or 'triangles' not in refs:
        raise ValueError('Invalid CAD preview cache metadata.')
    if set(payload)&{*_GROUPS,'edges'} or not set(refs)<=set(_GROUPS):
        raise ValueError('Invalid CAD preview cache keys.')
    used=set()
    for group,roles in refs.items():
        if not isinstance(roles,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in roles.items()):
            raise ValueError('Invalid CAD preview cache references.')
        if any(not re.fullmatch('a[0-9]+',value) or value not in arrays for value in roles.values()):
            raise ValueError('Missing CAD preview cache array.')
        # The worker's canonical preview.json sorts object keys. Preserve its
        # draw order rather than OCCT's face-discovery order at equal depth.
        payload[group]={role:arrays[key] for role,key in sorted(roles.items())};used.update(roles.values())
    if set(arrays)-{'edge_points','edge_offsets'}!=used:raise ValueError('Unused CAD preview cache arrays.')
    points=arrays['edge_points'];offsets=arrays['edge_offsets']
    if offsets[0]!=0 or offsets[-1]!=len(points) or np.any(offsets[1:]<offsets[:-1]):
        raise ValueError('Invalid CAD preview edge offsets.')
    for array in arrays.values():
        if not np.isfinite(array).all():raise ValueError('Non-finite CAD preview cache coordinates.')
        array.setflags(write=False)
    payload['edges']=[points[a:b] for a,b in zip(offsets[:-1],offsets[1:])]
    _validate_payload(payload)
    return payload


def load_preview(job):
    job=Path(job);warning=None
    if (job/'preview.cache.npz').is_file():
        try:return read_preview_cache(job),None
        except (OSError,ValueError,KeyError,TypeError,OverflowError,EOFError,zipfile.BadZipFile) as exc:
            warning='CAD preview cache ignored: '+str(exc)
    payload=json.loads((job/'preview.json').read_text(encoding='utf-8'));_validate_payload(payload)
    return payload,warning
