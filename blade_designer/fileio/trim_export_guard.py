"""Reject unsupported derivative exports before creating any output."""
from ..geometry.impeller_trim import trim_active


def guard_trim_export(params):
    if trim_active(params.impeller_trim):
        raise ValueError('Impeller trim: TurboGrid/CAD export is not supported yet. Disable trim or export the source design separately.')
