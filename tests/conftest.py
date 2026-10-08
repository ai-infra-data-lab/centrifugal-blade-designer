import pytest
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.designer import BladeDesigner


@pytest.fixture(scope="session")
def default_blade():
    return BladeDesigner().generate(BladeParameters())
