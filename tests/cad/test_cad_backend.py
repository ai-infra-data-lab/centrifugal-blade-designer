import sys
from blade_designer.cad.client import backend_python

def test_kernel_is_optional_in_editing_process():
    assert "OCP" not in sys.modules

def test_actual_backend_version_and_valid_brep(native_blade):
    r=native_blade['report'];assert r['backend_version']=='8.0.1.1.0'
    assert r['checks']['result']['brep_valid'] and r['checks']['result']['closed_shell']
