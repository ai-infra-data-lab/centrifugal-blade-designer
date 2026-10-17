import numpy as np

def test_independent_disk_has_analytic_volume(native_assembly):
    m=native_assembly['report']['checks']['hub_solid']
    assert m['solid_count']==1
    assert np.isclose(m['volume_mm3'],np.pi*(250**2-20**2)*40,rtol=1e-8)
