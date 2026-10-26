"""Preserve pre-option snapshot bytes without mutating caller-owned dictionaries."""


def canonical_sector_defaults(value):
    if isinstance(value,dict):
        row={'identifier','kind','parameters'}<=value.keys()
        omitted=set()
        if row and value.get('independent_meridional') is False:omitted.add('independent_meridional')
        if row and value.get('upstream_row',False) is None:omitted.add('upstream_row')
        for key in ('inlet_turn_deg','hub_inlet_turn_deg','shroud_inlet_turn_deg'):
            if value.get(key,False) is None:omitted.add(key)
        cad=('mechanical_scope' in value and 'fillet' in value and 'disk' in value)
        if cad and value.get('sector_boundary')=='fixed':
            omitted.add('sector_boundary')
        updates={}
        for key,child in value.items():
            if isinstance(child,dict):updated=canonical_sector_defaults(child)
            elif key in ('blade_rows','segments') and isinstance(child,list):
                updated=[canonical_sector_defaults(row) for row in child]
                if all(a is b for a,b in zip(updated,child)):updated=child
            else:updated=child
            if updated is not child:updates[key]=updated
        if updates or omitted:return {key:updates.get(key,child) for key,child in value.items() if key not in omitted}
    return value
