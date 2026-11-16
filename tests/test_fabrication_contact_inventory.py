"""Source-to-IPC-D-356 component-pad identity inventory regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import Contact, UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_contact_inventory import (
    require_ipc356_source_pad_inventory,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_BOARD = Path(__file__).parent / "fixtures/fabrication-connectivity/clean.kicad_pcb"


def _contact(pin: str, net: str = "SIGNAL") -> Contact:
    return Contact(net, "J1", pin, 5.0 if pin == "1" else 7.0, 5.0, "top", 1.0)


def test_complete_component_pad_and_net_inventory_matches_source() -> None:
    board = _BOARD.read_text(encoding="utf-8")

    require_ipc356_source_pad_inventory(board, (_contact("1"), _contact("2")))


def test_no_connect_pad_contact_is_optional_but_must_match_source() -> None:
    board = _BOARD.read_text(encoding="utf-8").replace(
        '(pad "2" smd circle (at 2 0) (size 1 1) (layers "F.Cu" "F.Mask") (net 1 "SIGNAL"))',
        '(pad "2" smd circle (at 2 0) (size 1 1) (layers "F.Cu" "F.Mask"))',
    )

    require_ipc356_source_pad_inventory(
        board,
        (
            _contact("1"),
            Contact("N/C:J1:2", "J1", "2", 7.0, 5.0, "top", 1.0),
        ),
    )
    require_ipc356_source_pad_inventory(board, (_contact("1"),))


@pytest.mark.parametrize(
    "contacts",
    [
        (_contact("1"),),
        (_contact("1"), _contact("2", "OTHER")),
        (_contact("1"), _contact("2"), _contact("3")),
        (_contact("1"), _contact("1")),
    ],
    ids=("omitted-pad", "reassigned-net", "unknown-pad", "duplicate-contact"),
)
def test_incomplete_or_mismatched_inventory_fails_closed(
    contacts: tuple[Contact, ...],
) -> None:
    board = _BOARD.read_text(encoding="utf-8")

    with pytest.raises(UnsupportedFabricationFormat, match="contact inventory differs"):
        require_ipc356_source_pad_inventory(board, contacts)
