from copy import deepcopy
import numpy as np
from blade_designer.cad.client import prepare_job
from .conftest import sample_parameters

def test_all_master_points_respect_cad_tolerance(native_blade):
    r=native_blade['report'];assert r['cad_surface_status']=='PASS'
    for role,error in r['checks']['blade_solids']['main']['master_deviation_mm'].items():assert error<=.01

def test_export_counts_do_not_change_cad_inputs(tmp_path):
    p=sample_parameters();a=prepare_job(p,'generate',tmp_path/'a')
    p.output_points.ps_points=51;p.output_points.le_points=11;b=prepare_job(p,'generate',tmp_path/'b')
    with np.load(a/'geometry.npz') as x,np.load(b/'geometry.npz') as y:
        assert x.files==y.files
        for key in x.files:np.testing.assert_array_equal(x[key],y[key])
