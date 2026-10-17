"""Identity of a generated result; never persisted as a design parameter."""
from dataclasses import dataclass


@dataclass(frozen=True)
class GeometrySource:
    row_id: str
    row_name: str
    row_kind: str
    engine: str
    variant: str
    snapshot_hash: str

    @property
    def label(self):
        return f'{self.row_name} [{self.row_id}] | {self.engine} / {self.variant} | {self.snapshot_hash[:12]}'
