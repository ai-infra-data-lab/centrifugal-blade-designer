from copy import deepcopy
from blade_designer.models.parameters import BladeParameters,BladeSection,EdgeType


def test_independent_sections_and_legacy_alias():
 p=BladeParameters()
 assert [s.span for s in p.sections]==[0,1]
 assert p.sections[0].blade_angle is p.blade_angle
 p.sections[1].blade_angle.points[1].value=25
 p.sections[1].thickness.points[1].value=7
 p.sections[1].edge_parameters.le_type=EdgeType.CUTOFF
 assert p.blade_angle.points[1].value==62
 assert p.thickness.points[1].value==4
 assert p.edges.le_type==EdgeType.CIRCULAR
 p.sections.insert(1,BladeSection(.5))
 assert [s.span for s in p.sections]==[0,.5,1]
 q=deepcopy(p);assert q.sections[0].blade_angle is q.blade_angle


def test_replace_distributions_from_either_api_saves_canonical_hub(tmp_path):
 from blade_designer.models.parameters import BladeAngleParameters,ThicknessParameters,DistributionPoint
 from blade_designer.fileio.project_io import save_project,load_project
 p=BladeParameters(sections=[BladeSection(0),BladeSection(1)])
 p.sections[0].blade_angle=BladeAngleParameters([DistributionPoint(0,40),DistributionPoint(1,20)])
 assert p.blade_angle is p.sections[0].blade_angle
 p.thickness=ThicknessParameters([DistributionPoint(0,1),DistributionPoint(1,2)])
 assert p.sections[0].thickness is p.thickness
 save_project(tmp_path/'custom.json',p)
 q=load_project(tmp_path/'custom.json')
 assert q==p and q.sections[0].blade_angle is q.blade_angle
 assert q.sections[1].blade_angle.points[0].value==65
