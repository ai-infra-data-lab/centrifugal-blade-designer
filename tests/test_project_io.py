import json
import pytest
from blade_designer.models.parameters import BladeParameters, EdgeType, SurfaceMapping
from blade_designer.fileio.project_io import save_project, load_project


def test_roundtrip(tmp_path):
    p = BladeParameters()
    p.geometry.r_le = 100.12345678901234
    p.edges.le_type = EdgeType.ELLIPTICAL
    p.edges.le_ellipse_ratio = 2.5
    p.surface_mapping = SurfaceMapping.NEGATIVE_IS_PS
    p.export.significant_digits = 3
    path = tmp_path/"翼.json"
    save_project(path,p)
    assert load_project(path) == p
    assert json.loads(path.read_text(encoding="utf-8"))["geometry"]["r_le"] == p.geometry.r_le


@pytest.mark.parametrize("kind",["version","missing","enum","points","nan"])
def test_invalid_project(tmp_path,kind):
    path = tmp_path/"bad.json"
    save_project(path,BladeParameters())
    data = json.loads(path.read_text())
    if kind == "version": data["schema_version"] = "9"
    if kind == "missing": del data["geometry"]["r_le"]
    if kind == "enum": data["edges"]["le_type"] = "unknown"
    if kind == "points": data["blade_angle"]["points"] = "bad"
    if kind == "nan": data["geometry"]["r_le"] = float("nan")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): load_project(path)
