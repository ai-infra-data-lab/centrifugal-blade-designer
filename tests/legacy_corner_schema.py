"""Reconstruct the pre-corner schema for existing byte-compatibility checks."""
from copy import deepcopy


def pre_corner_schema(value):
    value=deepcopy(value)
    def visit(item):
        if isinstance(item,dict):
            for key in ('inlet_turn_deg','hub_inlet_turn_deg','shroud_inlet_turn_deg'):
                if key in item:
                    assert item[key] is None,'Only new default fields can be removed from a legacy reference.'
                    del item[key]
            for child in item.values():visit(child)
        elif isinstance(item,list):
            for child in item:visit(child)
    visit(value)
    return value
