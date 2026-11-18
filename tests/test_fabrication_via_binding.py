"""IPC-D-356 VIA records must match source PCB via inventory and centers."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import Contact, UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_via_binding import (
    SourceVia,
    require_ipc356_source_via_geometry,
    require_ipc356_source_via_inventory,
    source_board_vias,
)
from kicad_tooling.hwrepo.pcb_board_net_inventory import pcb_board_net_map

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_FIXTURES = Path(__file__).parent / "fixtures/fabrication-connectivity"


def _via_contact(x_mm: float = 6.0, y_mm: float = -5.0, net: str = "SIGNAL") -> Contact:
    return Contact(net, "VIA", "via", x_mm, y_mm, "through", 0.7, size_x_mm=0.7, size_y_mm=0.0)


def test_source_via_net_code_and_board_center_match_ipc356() -> None:
    board = (_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8")
    source_vias = source_board_vias(board)

    assert source_vias == (SourceVia("SIGNAL", 6_000_000, 5_000_000, 300_000, 700_000),)
    require_ipc356_source_via_inventory(source_vias, (_via_contact(),))
    require_ipc356_source_via_geometry(source_vias, (_via_contact(),))


def test_source_board_without_vias_accepts_no_via_contacts() -> None:
    board = (_FIXTURES / "clean.kicad_pcb").read_text(encoding="utf-8")

    require_ipc356_source_via_inventory(source_board_vias(board), ())


@pytest.mark.parametrize(
    ("source_contacts", "message"),
    [
        ((), "count differs"),
        ((_via_contact(net="RETURN"),), "no matching source via"),
        ((_via_contact(x_mm=6.5),), "no matching source via"),
        ((_via_contact(), _via_contact()), "count differs"),
    ],
    ids=("missing-record", "wrong-net", "moved-record", "duplicate-record"),
)
def test_missing_moved_or_wrong_via_records_fail_closed(
    source_contacts: tuple[Contact, ...], message: str
) -> None:
    board = (_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8")
    source_vias = source_board_vias(board)

    with pytest.raises(UnsupportedFabricationFormat, match=message):
        require_ipc356_source_via_inventory(source_vias, source_contacts)


@pytest.mark.parametrize("delta_nm", (1_270, -1_270))
def test_via_center_rounding_within_cust0_tolerance_is_allowed(delta_nm: int) -> None:
    board = (_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8")
    source_vias = source_board_vias(board)

    require_ipc356_source_via_inventory(
        source_vias, (_via_contact(x_mm=6.0 + delta_nm / 1_000_000),)
    )


def test_via_center_rounding_outside_cust0_tolerance_is_rejected() -> None:
    board = (_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8")

    with pytest.raises(UnsupportedFabricationFormat, match="no matching source via"):
        require_ipc356_source_via_inventory(
            source_board_vias(board), (_via_contact(x_mm=6.001272),)
        )


def test_close_same_net_source_vias_are_rejected_as_ambiguous() -> None:
    board = (
        (_FIXTURES / "via.kicad_pcb")
        .read_text(encoding="utf-8")
        .replace(
            "\n  (gr_line",
            "\n  (via (at 6.002 5) (size 0.7) (drill 0.3) "
            '(layers "F.Cu" "B.Cu") (net 1))\n  (gr_line',
            1,
        )
    )
    source_vias = source_board_vias(board)

    with pytest.raises(UnsupportedFabricationFormat, match="ambiguous source match"):
        require_ipc356_source_via_inventory(
            source_vias, (_via_contact(x_mm=6.0), _via_contact(x_mm=6.001))
        )


def test_source_via_with_unknown_net_code_fails_closed() -> None:
    board = (
        (_FIXTURES / "via.kicad_pcb")
        .read_text(encoding="utf-8")
        .replace(
            '(net 1) (uuid "00000000-0000-0000-0000-000000000101")',
            '(net 99) (uuid "00000000-0000-0000-0000-000000000101")',
        )
    )

    with pytest.raises(UnsupportedFabricationFormat, match="unknown net assignment"):
        source_board_vias(board)


def test_source_via_without_one_positive_drill_size_fails_closed() -> None:
    board = (_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8")

    for invalid in ("(drill 0)", "(drill 0.3 0.4)"):
        malformed = board.replace("(drill 0.3)", invalid, 1)
        with pytest.raises(UnsupportedFabricationFormat, match="drill size"):
            source_board_vias(malformed)


def test_named_net_map_retains_numeric_codes_for_source_objects() -> None:
    board = (_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8")

    assert pcb_board_net_map(board) == ((0, ""), (1, "SIGNAL"), (2, "RETURN"))
