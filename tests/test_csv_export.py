import csv
from collections import Counter
import numpy as np
from blade_designer.fileio.csv_export import export_segments_csv, export_contour_csv, format_number
from blade_designer.models.parameters import ExportParameters


def test_exports(default_blade,tmp_path):
    b = default_blade
    before = b.surfaces.ps.xy.copy()
    path = tmp_path/"segments.csv"
    export_segments_csv(path,b)
    with path.open() as f: rows = list(csv.DictReader(f))
    assert Counter(r["segment"] for r in rows) == {"LE":21,"PS":101,"TE":21,"SS":101}
    assert rows[0]["m_norm"] == "" and rows[0]["curvature"] == ""
    ps = [r for r in rows if r["segment"] == "PS"]
    # G1 rounding trims PS/SS on their original distribution coordinate.
    # Do not renormalize it to 0/1 and move the angle/thickness data.
    assert ps[0]["m_norm"] == format(float(b.surfaces.ps.m_norm[0]),".6g")
    assert ps[-1]["m_norm"] == format(float(b.surfaces.ps.m_norm[-1]),".6g")
    assert ps[0]["segment_fraction"] == "0" and ps[-1]["segment_fraction"] == "1"
    assert ps[0]["x"] == format(float(b.surfaces.ps.x[0]),".6g")
    export_contour_csv(tmp_path/"contour.csv",b)
    with (tmp_path/"contour.csv").open() as f: contour = list(csv.DictReader(f))
    assert len(contour) == 240
    export_contour_csv(tmp_path/"repeat.csv",b,ExportParameters(8,True))
    with (tmp_path/"repeat.csv").open() as f: repeated = list(csv.DictReader(f))
    assert len(repeated) == 241 and repeated[0]["x"] == repeated[-1]["x"]
    export_segments_csv(path,b,ExportParameters(3))
    np.testing.assert_array_equal(b.surfaces.ps.xy,before)


def test_precision():
    assert format_number(123.456789,6) == "123.457"
    assert format_number(1.23456789,6) == "1.23457"
    assert format_number(.001234567,6) == "0.00123457"
