from copy import deepcopy
from test_cad_gui import window
from blade_designer.models.cad import SectorBoundaryMode


def test_following_selection_undo_redo_save_and_row_switch(window,tmp_path):
    w=window;before=deepcopy(w.get_parameters())
    assert not w.cad_editor.sector_boundary.isEnabled()
    w.cad_editor.scope.setCurrentIndex(w.cad_editor.scope.findData('periodic_sector'))
    w.commit_edit()
    assert w.cad_editor.sector_boundary.isEnabled()
    fixed=deepcopy(w.get_parameters())
    w.cad_editor.sector_boundary.setCurrentIndex(w.cad_editor.sector_boundary.findData('blade_following'))
    w.commit_edit();following=deepcopy(w.get_parameters())
    assert following.cad_export.sector_boundary is SectorBoundaryMode.BLADE_FOLLOWING
    w.undo();assert w.get_parameters()==fixed
    w.redo();assert w.get_parameters()==following
    target=tmp_path/'project.json';w.save_to_path(target)
    w.new_project();w.load_from_path(target)
    assert w.get_parameters().cad_export.sector_boundary is SectorBoundaryMode.BLADE_FOLLOWING
    w.set_parameters(before)
    assert w.get_parameters()==before
