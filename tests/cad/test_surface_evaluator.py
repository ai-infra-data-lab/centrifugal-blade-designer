"""Actual OCCT evaluation at interior span points, in the isolated backend."""
import subprocess
import pytest
from blade_designer.cad.client import backend_python, ROOT


@pytest.mark.parametrize('clamped', [False, True])
def test_occt_surface_matches_shared_numeric_evaluator(clamped):
    from blade_designer.cad.errors import BackendUnavailableError
    try:python = backend_python()
    except BackendUnavailableError as exc:pytest.skip('Optional CAD backend unavailable: '+str(exc))
    script = '''
import numpy as np
from blade_designer.cad.occt_backend import OcctBackend
from blade_designer.geometry.surface_evaluation import fit_surface_spline
spans=np.array([0.,.2,.7,1.]);t=np.linspace(0,1,33)
rows=[np.column_stack((t,t**3+s**3,np.full(len(t),s))) for s in spans]
tangents=np.array([[[1,0,0]]*4,[[1,3,0]]*4],dtype=float) if CLAMPED else None
numeric=fit_surface_spline(rows,33,spans=spans,tangents=tangents)
cad=OcctBackend().create_surface(rows,33,spans=spans,tangents=tangents)
ss=np.linspace(0,1,23);tt=np.linspace(0,1,29)
expected=numeric.evaluate_grid(ss,tt)
observed=np.array([[[p.X(),p.Y(),p.Z()] for p in [cad.Value(float(s),float(x)) for x in tt]] for s in ss])
np.testing.assert_allclose(observed,expected,atol=2e-14,rtol=0)
'''.replace('CLAMPED', str(clamped))
    result = subprocess.run([str(python), '-X', 'utf8', '-c', script], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', timeout=90)
    assert result.returncode == 0, result.stdout+result.stderr
