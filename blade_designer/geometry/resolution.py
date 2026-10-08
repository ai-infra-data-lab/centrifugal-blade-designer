from dataclasses import asdict

def validate_resolution(parameters):
    minimum={"profile_points":101,"edge_points":11,"wall_points":501,"mean_points":501,"area_points":21}
    for name,value in asdict(parameters).items():
        if not isinstance(value,int) or isinstance(value,bool) or not minimum[name]<=value<=40001:
            raise ValueError(f"{name} requires an integer in [{minimum[name]},40001].")
    if parameters.edge_points%2!=1:
        raise ValueError("Internal edge resolution must be odd to retain the edge midpoint.")
