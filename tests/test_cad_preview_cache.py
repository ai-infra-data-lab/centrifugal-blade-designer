import io,json,zipfile
import numpy as np
import pytest
from blade_designer.cad.preview_cache import write_preview_cache,read_preview_cache,load_preview


def data():
    triangle=[[[1.,2.,3.],[4.,5.,6.],[7.,8.,9.]]]
    return {'triangles':{'BLADE_PS':triangle,'EMPTY':[]},'triangles_full':{'BLADE_PS':triangle},
        'edges':[[[0.,1.,2.],[3.,4.,5.]],[]],'snapshot_hash':'design-snapshot','scope':'full_impeller',
        'blade_count':11,'fillet_radius_mm':.1}


def source(tmp_path):
    payload=data();(tmp_path/'preview.json').write_text(json.dumps(payload),encoding='utf-8')
    return payload


def test_lossless_cache_readonly_shared_arrays_and_original_json_unchanged(tmp_path):
    payload=source(tmp_path);before=(tmp_path/'preview.json').read_bytes();write_preview_cache(payload,tmp_path)
    result=read_preview_cache(tmp_path)
    assert (tmp_path/'preview.json').read_bytes()==before
    for group in ('triangles','triangles_full'):
        for role,rows in payload[group].items():
            np.testing.assert_array_equal(result[group][role],np.asarray(rows).reshape(-1,3,3))
            assert not result[group][role].flags.writeable
    assert result['triangles']['BLADE_PS'] is result['triangles_full']['BLADE_PS']
    for a,b in zip(result['edges'],payload['edges']):np.testing.assert_array_equal(a,np.asarray(b).reshape(-1,3))
    assert result['snapshot_hash']=='design-snapshot' and result['blade_count']==11


def test_old_json_without_cache_remains_supported(tmp_path):
    payload=source(tmp_path);result,warning=load_preview(tmp_path)
    assert result==payload and warning is None


def test_stale_or_corrupt_cache_uses_json_and_reports_warning(tmp_path):
    payload=source(tmp_path);write_preview_cache(payload,tmp_path)
    payload['blade_count']=12;(tmp_path/'preview.json').write_text(json.dumps(payload)+'\n',encoding='utf-8')
    result,warning=load_preview(tmp_path);assert result==payload and 'Stale' in warning
    (tmp_path/'preview.cache.npz').write_bytes(b'not a zip')
    result,warning=load_preview(tmp_path);assert result==payload and warning


@pytest.mark.parametrize('corruption',['nan','object','offset','metadata','unused','missing'])
def test_invalid_cache_never_replaces_compatibility_payload(tmp_path,corruption):
    payload=source(tmp_path);write_preview_cache(payload,tmp_path);path=tmp_path/'preview.cache.npz'
    with np.load(path,allow_pickle=False) as stored:arrays={key:stored[key] for key in stored.files}
    if corruption=='nan':arrays['a0'][0,0,0]=float('nan')
    elif corruption=='object':arrays['a0']=np.array([object()],dtype=object)
    elif corruption=='offset':arrays['edge_offsets'][-1]+=1
    elif corruption=='metadata':arrays['meta']=np.frombuffer(b'null',dtype=np.uint8)
    elif corruption=='unused':arrays['a999']=np.ones((1,3,3))
    elif corruption=='missing':del arrays['a0']
    np.savez_compressed(path,**arrays)
    result,warning=load_preview(tmp_path);assert result==payload and warning


def test_huge_npy_header_rejected_before_array_allocation(tmp_path,monkeypatch):
    source(tmp_path);stream=io.BytesIO()
    np.lib.format.write_array_header_1_0(stream,{'descr':'<f8','fortran_order':False,'shape':(10**10,3,3)})
    with zipfile.ZipFile(tmp_path/'preview.cache.npz','w') as archive:archive.writestr('a0.npy',stream.getvalue())
    def forbidden(*args,**kwargs):raise AssertionError('Unbounded array was allocated')
    monkeypatch.setattr(np.lib.format,'read_array',forbidden)
    with pytest.raises(ValueError,match='length'):read_preview_cache(tmp_path)


def test_writer_rejects_nonfinite_points(tmp_path):
    payload=source(tmp_path);payload['triangles']['BLADE_PS'][0][0][0]=float('inf')
    with pytest.raises(ValueError,match='coordinates'):write_preview_cache(payload,tmp_path)
    assert not (tmp_path/'preview.cache.npz').exists()
