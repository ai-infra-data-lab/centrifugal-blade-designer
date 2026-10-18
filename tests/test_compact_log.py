import hashlib
import io
import zipfile
import pytest
from tools.compact_log import render_output
from tools.install_rtk import verified_members


@pytest.mark.parametrize('code,summary', [
    (1, {'report_status':'read','passed':1,'failed':1}),
    (2, {'report_status':'read','errors':1}),
    (0, {'report_status':'read','passed':1,'skipped':1}),
    (0, {'report_status':'unavailable','passed':1}),
    (5, {'report_status':'read','passed':0}),
    (0, {'report_status':'read','passed':0}),
])
def test_unsuccessful_or_incomplete_results_never_reach_compressor(code, summary):
    def forbidden(_): raise AssertionError('Must preserve raw failure/skip detail')
    assert render_output('COMPLETE DETAILS',code,summary,forbidden) == ('COMPLETE DETAILS',False)


def test_success_can_compress_and_tool_failure_falls_back_to_raw():
    summary = dict(report_status='read',passed=10)
    assert render_output('ten test lines',0,summary,lambda _: '10 passed') == ('10 passed',True)
    def missing(_): raise FileNotFoundError('RTK absent')
    assert render_output('ten test lines',0,summary,missing) == ('ten test lines',False)


@pytest.mark.parametrize('bad', ['archive', 'executable', None])
def test_checksum_validation_precedes_installation_and_only_reads_named_members(bad):
    content = io.BytesIO()
    with zipfile.ZipFile(content,'w') as archive:
        archive.writestr('rtk.exe',b'EXE')
        archive.writestr('LICENSE',b'license')
        archive.writestr('../outside.txt',b'NEVER EXTRACT')
    data = content.getvalue()
    release = dict(archive_sha256=hashlib.sha256(data).hexdigest(),exe_sha256=hashlib.sha256(b'EXE').hexdigest())
    if bad: release[bad+'_sha256' if bad=='archive' else 'exe_sha256'] = '0'*64
    if bad:
        with pytest.raises(ValueError, match='checksum'): verified_members(data,release)
    else:
        assert verified_members(data,release) == (b'EXE',b'license')
