"""IPC-D-356 contact layers must agree with source PCB pad copper access."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Literal

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    Contact,
    UnsupportedFabricationFormat,
    parse_ipc356,
)
from kicad_tooling.hwrepo.fabrication_contact_layers import (
    require_ipc356_source_pad_access_codes,
    require_ipc356_source_pad_layers,
)
from kicad_tooling.hwrepo.fabrication_contact_source import (
    SourceComponentPad,
    source_component_pads,
)
from tests.fabrication_connectivity_support import format_ipc_contact

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_FIXTURES = Path(__file__).parent / "fixtures/fabrication-connectivity"
_REPEATED_LAYER_FIXTURE = _FIXTURES / "repeated-pad-layer-classes.kicad_pcb"
_Layer = Literal["top", "bottom", "through"]


def _source(side: str) -> tuple[SourceComponentPad, ...]:
    if side == "through":
        board = (_FIXTURES / "multilayer/four-layer-clean.kicad_pcb").read_text(encoding="utf-8")
    elif side == "bottom-four-layer":
        board = (_FIXTURES / "multilayer/four-layer-bottom-pad-access-code.kicad_pcb").read_text(
            encoding="utf-8"
        )
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


def _source_contacts(source: tuple[SourceComponentPad, ...]) -> tuple[Contact, ...]:
    contacts: list[Contact] = []
    for pad in source:
        if pad.contact_layer is None:
            raise AssertionError("fixture pad must have an identifiable contact layer")
        contacts.append(
            Contact(
                pad.net_name or f"N/C:{pad.reference}:{pad.number}",
                pad.reference,
                pad.number,
                pad.x_nm / 1_000_000,
                -pad.y_nm / 1_000_000,
                pad.contact_layer,
                (pad.size_x_nm or 0) / 1_000_000,
                size_x_mm=(pad.size_x_nm or 0) / 1_000_000,
                size_y_mm=0.0 if pad.pad_shape == "circle" else (pad.size_y_nm or 0) / 1_000_000,
                access_code={"through": 0, "top": 1, "bottom": 2}[pad.contact_layer],
            )
        )
    return tuple(contacts)


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


def test_repeated_pin_contact_layers_remain_bound_to_source_centers() -> None:
    board = _REPEATED_LAYER_FIXTURE.read_text(encoding="utf-8")
    source = source_component_pads(board)
    assert tuple(pad.contact_layer for pad in source) == ("top", "through")
    matching = _source_contacts(source)
    require_ipc356_source_pad_layers(source, matching)

    swapped = (
        replace(matching[0], layer="through"),
        replace(matching[1], layer="top"),
    )
    with pytest.raises(UnsupportedFabricationFormat, match="layer classification differs"):
        require_ipc356_source_pad_layers(source, swapped)


@pytest.mark.parametrize(
    ("source_side", "access_code", "copper_layer_count"),
    (
        ("top", 1, 2),
        ("bottom", 2, 2),
        ("bottom-four-layer", 4, 4),
        ("through", 0, 4),
    ),
)
def test_numeric_access_code_matches_source_pad_and_copper_stack(
    source_side: str, access_code: int, copper_layer_count: int
) -> None:
    source = _source(source_side)
    contacts = tuple(
        replace(contact, access_code=access_code) for contact in _source_contacts(source)
    )

    require_ipc356_source_pad_access_codes(source, contacts, copper_layer_count)


@pytest.mark.parametrize(
    ("source_side", "access_code", "copper_layer_count"),
    (
        ("top", 0, 2),
        ("top", 2, 2),
        ("bottom", 1, 2),
        ("bottom", 3, 2),
        ("bottom-four-layer", 3, 4),
        ("through", 1, 4),
    ),
)
def test_numeric_access_code_mismatch_fails_closed(
    source_side: str, access_code: int, copper_layer_count: int
) -> None:
    source = _source(source_side)
    contacts = tuple(
        replace(contact, access_code=access_code) for contact in _source_contacts(source)
    )

    with pytest.raises(UnsupportedFabricationFormat, match="access code differs"):
        require_ipc356_source_pad_access_codes(source, contacts, copper_layer_count)


@pytest.mark.parametrize(
    ("record_type", "access_code", "expected_layer"),
    (("317", 0, "through"), ("327", 0, "through"), ("327", 1, "top"), ("327", 2, "bottom")),
)
def test_ipc356_parser_retains_numeric_access_code_and_decodes_layer(
    record_type: str, access_code: int, expected_layer: _Layer
) -> None:
    record = format_ipc_contact(record_type, "SIGNAL", "J1", "1", access_code, 5.0)

    (contact,) = parse_ipc356(f"P  UNITS CUST 0\n{record}\n999\n")

    assert contact.layer == expected_layer
    assert contact.access_code == access_code
