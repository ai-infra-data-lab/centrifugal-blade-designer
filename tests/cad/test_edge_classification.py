def test_root_roles_and_fluid_boundary_roles_are_present(native_assembly):
    r=native_assembly['report'];assert r['checks']['fillet']['main']['root_edge_count']>=4
    artifact=r['artifacts']['turbogrid_cad']
    assert {'HUB','SHROUD','BLADE_PS','BLADE_SS','BLADE_LE','BLADE_TE','HUB_FILLET','INLET','OUTLET','PERIODIC_LOW','PERIODIC_HIGH'}<=set(artifact['boundary_roles'])
