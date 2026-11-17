"""Source matching for plated and non-plated component-pad drill hits."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_contact_source import (
    SourceComponentPad,
    source_component_pads,
)
from kicad_tooling.hwrepo.fabrication_excellon import DrillHit, parse_excellon
from kicad_tooling.hwrepo.fabrication_pad_drill_binding import (
    require_excellon_source_pad_drills,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_BOARD = Path(__file__).parent / "fixtures/fabrication-connectivity/drilled-pads.kicad_pcb"


def _drills(coordinates: tuple[str, ...], diameter: str) -> tuple[DrillHit, ...]:
    hits = "\n".join(coordinates)
    text = f"M48\nMETRIC,LZ\nT1C{diameter}\n%\nG90\nG05\nT1\n{hits}\nM30\n"
    return parse_excellon(text)


def test_component_drill_inventory_uses_footprint_rotation_and_pad_plating() -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))
    drilled = tuple(pad for pad in source if pad.drill_plating is not None)

    assert [
        (pad.reference, pad.number, pad.x_nm, pad.y_nm, pad.drill_nm, pad.drill_plating)
        for pad in drilled
    ] == [
        ("J2", "1", 10_000_000, 9_000_000, 800_000, "plated"),
        ("J2", "2", 10_000_000, 7_000_000, 1_000_000, "nonplated"),
    ]


def test_plated_and_nonplated_source_pad_drills_match_separate_outputs() -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))

    require_excellon_source_pad_drills(
        source,
        _drills(("X10.000Y-9.000",), "0.800"),
        _drills(("X10.000Y-7.000",), "1.000"),
    )


@pytest.mark.parametrize(
    ("plated", "plated_diameter", "nonplated", "nonplated_diameter", "reason"),
    (
        ((), "0.800", ("X10.000Y-7.000",), "1.000", "no circular drill hit at source pad J2.1"),
        (
            ("X10.100Y-9.000",),
            "0.800",
            ("X10.000Y-7.000",),
            "1.000",
            "no circular drill hit at source pad J2.1",
        ),
        (
            ("X10.000Y-9.000",),
            "0.900",
            ("X10.000Y-7.000",),
            "1.000",
            "drill diameter at source pad J2.1",
        ),
        (
            ("X10.000Y-7.000",),
            "0.800",
            ("X10.000Y-9.000",),
            "1.000",
            "no circular drill hit at source pad J2.1",
        ),
    ),
    ids=("missing-plated", "displaced-plated", "wrong-plated-size", "wrong-plating-file"),
)
def test_missing_moved_wrong_size_or_wrong_plating_pad_hit_fails_closed(
    plated: tuple[str, ...],
    plated_diameter: str,
    nonplated: tuple[str, ...],
    nonplated_diameter: str,
    reason: str,
) -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))

    with pytest.raises(UnsupportedFabricationFormat, match=reason):
        require_excellon_source_pad_drills(
            source,
            _drills(plated, plated_diameter),
            _drills(nonplated, nonplated_diameter),
        )


def test_one_excellon_hit_cannot_satisfy_two_source_pad_holes() -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))
    duplicate = SourceComponentPad(
        "J2", "3", "SIGNAL", "through", 10_000_000, 9_000_000, 800_000, "plated", "circular"
    )

    with pytest.raises(UnsupportedFabricationFormat, match="cannot uniquely bind"):
        require_excellon_source_pad_drills(
            (*source, duplicate),
            _drills(("X10.000Y-9.000",), "0.800"),
            _drills(("X10.000Y-7.000",), "1.000"),
        )


def test_source_oval_drill_fails_closed_until_slot_binding_is_supported() -> None:
    board = _BOARD.read_text(encoding="utf-8").replace("(drill 0.8)", "(drill oval 0.8 0.5)", 1)
    source = source_component_pads(board)

    with pytest.raises(UnsupportedFabricationFormat, match="unsupported drill shape"):
        require_excellon_source_pad_drills(
            source,
            _drills(("X10.000Y-9.000",), "0.800"),
            _drills(("X10.000Y-7.000",), "1.000"),
        )
