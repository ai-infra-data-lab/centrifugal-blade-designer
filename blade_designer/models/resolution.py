from dataclasses import dataclass

@dataclass
class GeometryResolutionParameters:
    profile_points: int = 2001
    edge_points: int = 401
    wall_points: int = 8001
    mean_points: int = 4001
    area_points: int = 501
