"""A success flag cannot replace radius evidence or make NaN acceptable."""
from copy import deepcopy
import pytest
from blade_designer.cad.cad_validation import require_fillet_samples
from blade_designer.cad.errors import CadExportError


def valid():
    return {'requested_radius_mm':.1,'faces':[{'status':'PASS','sampled_principal_radii_mm':[.1,.100001]}],
            'global_exact_radius':'NOT_TESTED','corner_radius_check':'NOT_APPLICABLE'}


def test_valid_samples_do_not_promote_global_or_corner_verification():
    report=valid();before=deepcopy(report)
    require_fillet_samples(report)
    assert report==before


@pytest.mark.parametrize('values',[[],[float('nan')],[float('inf')],[.12],[True]])
def test_bad_values_rejected_even_with_pass_flag(values):
    report=valid();report['faces'][0]['sampled_principal_radii_mm']=values
    with pytest.raises(CadExportError):require_fillet_samples(report)


@pytest.mark.parametrize('radius',[None,True,0.,-.1,float('nan'),float('inf')])
def test_invalid_requested_radius(radius):
    report=valid();report['requested_radius_mm']=radius
    with pytest.raises(CadExportError):require_fillet_samples(report)


@pytest.mark.parametrize('faces',[None,[],[{}],[{'status':'WARNING','sampled_principal_radii_mm':[.1]}]])
def test_missing_or_failed_face_evidence_rejected(faces):
    report=valid();report['faces']=faces
    with pytest.raises(CadExportError):require_fillet_samples(report)
