from copy import deepcopy
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from blade_designer.models.parameters import BladeParameters,BladeSection
from blade_designer.geometry.geometry_3d import generate_impeller
from blade_designer.geometry.wireframe import build_spanwise_wireframe
from blade_designer.gui.preview_3d import Preview3D

@pytest.mark.parametrize("spans",[[0,1],[0,.25,.5,.75,1]])
def test_local_segment_correspondence(spans):
    p=BladeParameters();p.sections=[BladeSection(span) for span in spans]
    p.sections[-1].blade_angle.points[1].value=30
    p.sections[-1].thickness.points[1].value=6
    g=generate_impeller(p);lines=build_spanwise_wireframe(g.sections)
    assert len(lines)==21+101+21+101
    for line in lines:
        count=len(getattr(g.sections[0],line.segment.lower()).r)
        assert line.segment_fraction==line.segment_index/(count-1)
        np.testing.assert_array_equal(line.spans,spans)
        for i,section in enumerate(g.sections):
            np.testing.assert_array_equal(line.xyz[i],getattr(section,line.segment.lower()).xyz[line.segment_index])

def test_mismatch_is_an_error():
    g=generate_impeller(BladeParameters());g.sections[1].ps.r=g.sections[1].ps.r[:-1]
    with pytest.raises(ValueError,match="mismatch|PS"):build_spanwise_wireframe(g.sections)

def test_preview_controls_and_camera_preservation():
    app=QApplication.instance() or QApplication([])
    preview=Preview3D();g=generate_impeller(BladeParameters())
    preview.update_geometry(g);preview.camera_position["azimuth"]=79
    camera=deepcopy(preview.camera_position)
    assert len(preview.spanwise_lines)==244
    assert all(box.isChecked() for box in preview.visibility_controls.values())
    for box in preview.visibility_controls.values():box.setChecked(False)
    assert list(preview.visible_lines())==[]
    for box in preview.visibility_controls.values():box.setChecked(True)
    preview.update_geometry(g)
    assert len(list(preview.visible_lines()))==254
    assert len(list(preview.visible_surfaces()))==2
    for k,value in camera.items():np.testing.assert_array_equal(preview.camera_position[k],value)
    previous=preview.lines
    g.sections[1].ps.r=g.sections[1].ps.r[:-1]
    with pytest.raises(ValueError):preview.update_geometry(g)
    assert preview.lines is previous
    preview.close()
