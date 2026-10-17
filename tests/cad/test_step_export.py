import hashlib

def test_only_verified_nonempty_step_is_staged(native_blade):
    job=native_blade['job'];artifact=native_blade['report']['artifacts']['mechanical']
    for name in artifact['files']:
        path=job/'outputs'/name;assert path.stat().st_size>100
        assert hashlib.sha256(path.read_bytes()).hexdigest()==artifact['sha256'][name]
