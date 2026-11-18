"""Per-layer copper evidence for through-hole fabrication contacts."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import Contact, GerberFeature, GerberLayer
from kicad_tooling.hwrepo.fabrication_connectivity_raster import analyze_raster

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


_LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def _layer(name: str, *, has_contact_copper: bool) -> GerberLayer:
    features = (
        (
            GerberFeature(
                "flash",
                ((5.0, -5.0),),
                aperture=("C", (0.8,)),
            ),
        )
        if has_contact_copper
        else ()
    )
    return GerberLayer(name, name, features)


def test_full_stack_contact_has_copper_on_every_source_layer() -> None:
    contact = Contact("SIGNAL", "J1", "1", 5.0, -5.0, "through", 1.0)
    layers = tuple(_layer(name, has_contact_copper=True) for name in _LAYERS)

    result = analyze_raster(layers, (contact,), (), density=50)

    assert result.assignments[0].components
    assert result.assignments[0].missing_layers == ()


def test_full_stack_contact_reports_the_specific_layer_without_copper() -> None:
    contact = Contact("SIGNAL", "J1", "1", 5.0, -5.0, "through", 1.0)
    layers = tuple(_layer(name, has_contact_copper=name != "In2.Cu") for name in _LAYERS)

    result = analyze_raster(layers, (contact,), (), density=50)

    assert result.assignments[0].components
    assert result.assignments[0].missing_layers == ("In2.Cu",)
    assert result.no_copper == ()
