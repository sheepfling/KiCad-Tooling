"""IPC-D-356 contact layers must agree with source PCB pad copper access."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import Contact, UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_contact_layers import require_ipc356_source_pad_layers
from kicad_tooling.hwrepo.fabrication_contact_source import (
    SourceComponentPad,
    source_component_pads,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_FIXTURES = Path(__file__).parent / "fixtures/fabrication-connectivity"
_Layer = Literal["top", "bottom", "through"]


def _source(side: str) -> tuple[SourceComponentPad, ...]:
    if side == "through":
        board = (_FIXTURES / "multilayer/four-layer-clean.kicad_pcb").read_text(encoding="utf-8")
    else:
        board = (_FIXTURES / "clean.kicad_pcb").read_text(encoding="utf-8")
        if side == "bottom":
            board = board.replace('(layer "F.Cu")', '(layer "B.Cu")', 1).replace(
                '"F.Cu" "F.Mask"', '"B.Cu" "B.Mask"'
            )
    return source_component_pads(board)


def _contacts(source: tuple[SourceComponentPad, ...], layer: _Layer) -> tuple[Contact, ...]:
    return tuple(
        Contact(
            pad.net_name or f"N/C:{pad.reference}:{pad.number}",
            pad.reference,
            pad.number,
            pad.x_nm / 1_000_000,
            -pad.y_nm / 1_000_000,
            layer,
            1.0,
        )
        for pad in source
    )


@pytest.mark.parametrize(
    ("source_side", "contact_layer"),
    (("top", "top"), ("bottom", "bottom"), ("through", "through")),
)
def test_contact_class_matches_source_pad_access(source_side: str, contact_layer: _Layer) -> None:
    source = _source(source_side)

    assert {pad.contact_layer for pad in source} == {contact_layer}
    require_ipc356_source_pad_layers(source, _contacts(source, contact_layer))


@pytest.mark.parametrize(
    ("source_side", "contact_layer"),
    (
        ("top", "bottom"),
        ("top", "through"),
        ("bottom", "top"),
        ("through", "top"),
        ("through", "bottom"),
    ),
)
def test_mismatched_contact_access_class_fails_closed(
    source_side: str, contact_layer: _Layer
) -> None:
    source = _source(source_side)

    with pytest.raises(UnsupportedFabricationFormat, match="layer classification differs"):
        require_ipc356_source_pad_layers(source, _contacts(source, contact_layer))


def test_dual_sided_smd_source_pad_is_unsupported_when_exported() -> None:
    board = (
        (_FIXTURES / "clean.kicad_pcb")
        .read_text(encoding="utf-8")
        .replace('"F.Cu" "F.Mask"', '"F.Cu" "B.Cu" "F.Mask" "B.Mask"')
    )
    source = source_component_pads(board)

    assert all(pad.contact_layer is None for pad in source)
    with pytest.raises(UnsupportedFabricationFormat, match="unsupported or ambiguous"):
        require_ipc356_source_pad_layers(source, _contacts(source, "top"))


def test_contact_without_matching_source_pad_fails_closed() -> None:
    contact = Contact("SIGNAL", "J9", "1", 1.0, -1.0, "top", 1.0)

    with pytest.raises(UnsupportedFabricationFormat, match="no unique source match"):
        require_ipc356_source_pad_layers((), (contact,))


def test_ipc356_via_records_are_not_component_pad_layer_matches() -> None:
    via = Contact("SIGNAL", "VIA", "via", 1.0, -1.0, "through", 0.7)

    require_ipc356_source_pad_layers((), (via,))
