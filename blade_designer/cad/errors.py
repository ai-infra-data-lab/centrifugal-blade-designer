class CadGeometryError(Exception):
    pass

class BackendUnavailableError(CadGeometryError):
    pass

class SurfaceConstructionError(CadGeometryError):
    pass

class BooleanUnionError(CadGeometryError):
    pass

class FilletGenerationError(CadGeometryError):
    pass

class InvalidSolidError(CadGeometryError):
    pass

class CadExportError(CadGeometryError):
    pass
