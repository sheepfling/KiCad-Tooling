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


def test_source_pad_shape_offset_binds_the_centered_oval_slot_geometry() -> None:
    board = _BOARD.read_text(encoding="utf-8")
    board = board.replace("(drill 0.8)", "(drill oval 1.0 0.6 (offset 0.2 0.1))", 1)
    board = board.replace("(drill 1.0)", "(drill oval 0.6 1.0 (offset 0.1 -0.2))", 1)
    source = source_component_pads(board)
    slot_pad = next(pad for pad in source if pad.reference == "J2" and pad.number == "1")
    nonplated_slot = next(pad for pad in source if pad.reference == "J2" and pad.number == "2")

    assert slot_pad.drill_shape == "oval"
    assert (slot_pad.x_nm, slot_pad.y_nm) == (10_000_000, 9_000_000)
    assert slot_pad.drill_width_nm == 1_000_000
    assert slot_pad.drill_height_nm == 600_000
    assert nonplated_slot.drill_shape == "oval"
    assert (nonplated_slot.x_nm, nonplated_slot.y_nm) == (10_000_000, 7_000_000)
    assert nonplated_slot.drill_width_nm == 600_000
    assert nonplated_slot.drill_height_nm == 1_000_000

    require_excellon_source_pad_drills(
        source,
        _drills(("X9.8Y-9.0G85X10.2Y-9.0",), "0.600"),
        _drills(("X10.0Y-6.8G85X10.0Y-7.2",), "0.600"),
    )


@pytest.mark.parametrize(
    ("slot", "diameter", "reason"),
    (
        ("X9.8Y-9.1G85X10.2Y-9.1", "0.600", "no oval drill hit at source pad J2.1"),
        ("X9.7Y-9.0G85X10.3Y-9.0", "0.600", "slot geometry at source pad J2.1"),
        ("X10.0Y-8.8G85X10.0Y-9.2", "0.600", "slot geometry at source pad J2.1"),
        ("X9.8Y-9.0G85X10.2Y-9.0", "0.700", "slot geometry at source pad J2.1"),
    ),
    ids=("displaced-slot", "wrong-length", "wrong-axis", "wrong-tool-size"),
)
def test_source_oval_drill_rejects_moved_or_wrong_geometry(
    slot: str, diameter: str, reason: str
) -> None:
    board = _BOARD.read_text(encoding="utf-8").replace("(drill 0.8)", "(drill oval 1.0 0.6)", 1)
    source = source_component_pads(board)

    with pytest.raises(UnsupportedFabricationFormat, match=reason):
        require_excellon_source_pad_drills(
            source,
            _drills((slot,), diameter),
            _drills(("X10.000Y-7.000",), "1.000"),
        )
