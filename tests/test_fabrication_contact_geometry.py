"""Source PCB pad centers must agree with IPC-D-356 contact coordinates."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import Contact, UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_contact_geometry import (
    require_ipc356_source_pad_coordinates,
)
from kicad_tooling.hwrepo.fabrication_contact_source import source_component_pads

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_BOARD = Path(__file__).parent / "fixtures/fabrication-connectivity/clean.kicad_pcb"


def _contact(pin: str, x_mm: float, y_mm: float) -> Contact:
    return Contact("SIGNAL", "J1", pin, x_mm, y_mm, "top", 1.0)


def _si_contact(pin: str, x_mm: float, y_mm: float) -> Contact:
    return Contact("SIGNAL", "J1", pin, x_mm, y_mm, "top", 1.0, 1_000)


def test_ipc356_centers_match_source_pad_centers() -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))

    require_ipc356_source_pad_coordinates(
        source, (_contact("1", 5.0, -5.0), _contact("2", 7.0, -5.0))
    )


def test_same_net_contact_moved_to_another_pad_is_rejected() -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))

    with pytest.raises(UnsupportedFabricationFormat, match="coordinates differ"):
        require_ipc356_source_pad_coordinates(
            source, (_contact("1", 5.0, -5.0), _contact("2", 5.0, -5.0))
        )


@pytest.mark.parametrize("delta_nm", (1_270, -1_270))
def test_ipc356_grid_rounding_within_half_step_is_allowed(delta_nm: int) -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))
    rounded_x = 5.0 + delta_nm / 1_000_000

    require_ipc356_source_pad_coordinates(
        source, (_contact("1", rounded_x, -5.0), _contact("2", 7.0, -5.0))
    )


@pytest.mark.parametrize("delta_nm", (1_272, -1_272))
def test_coordinate_error_outside_ipc356_rounding_tolerance_is_rejected(
    delta_nm: int,
) -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))
    outside_x = 5.0 + delta_nm / 1_000_000

    with pytest.raises(UnsupportedFabricationFormat, match="coordinates differ"):
        require_ipc356_source_pad_coordinates(
            source, (_contact("1", outside_x, -5.0), _contact("2", 7.0, -5.0))
        )


def test_si_coordinate_grid_uses_its_smaller_rounding_tolerance() -> None:
    source = source_component_pads(_BOARD.read_text(encoding="utf-8"))

    with pytest.raises(UnsupportedFabricationFormat, match="coordinates differ"):
        require_ipc356_source_pad_coordinates(
            source,
            (_si_contact("1", 5.000502, -5.0), _si_contact("2", 7.0, -5.0)),
        )


def test_footprint_rotation_transforms_pad_offsets_into_board_coordinates() -> None:
    board = _BOARD.read_text(encoding="utf-8").replace(
        '(layer "F.Cu") (at 5 5)', '(layer "F.Cu") (at 10 10 90)', 1
    )
    source = source_component_pads(board)

    assert {(pad.number, pad.x_nm, pad.y_nm) for pad in source} == {
        ("1", 10_000_000, 10_000_000),
        ("2", 10_000_000, 8_000_000),
    }
    require_ipc356_source_pad_coordinates(
        source, (_contact("1", 10.0, -10.0), _contact("2", 10.0, -8.0))
    )


def test_local_pad_y_offset_is_included_in_center_transform() -> None:
    board = _BOARD.read_text(encoding="utf-8").replace(
        "(at 2 0) (size 1 1)", "(at 0 2) (size 1 1)", 1
    )
    source = source_component_pads(board)

    assert {(pad.number, pad.x_nm, pad.y_nm) for pad in source} == {
        ("1", 5_000_000, 5_000_000),
        ("2", 5_000_000, 7_000_000),
    }
    require_ipc356_source_pad_coordinates(
        source, (_contact("1", 5.0, -5.0), _contact("2", 5.0, -7.0))
    )


def test_bottom_copper_footprint_uses_board_space_center_transform() -> None:
    board = _BOARD.read_text(encoding="utf-8").replace(
        '(layer "F.Cu") (at 5 5)', '(layer "B.Cu") (at 10 10 90)', 1
    )
    source = source_component_pads(board)

    require_ipc356_source_pad_coordinates(
        source, (_contact("1", 10.0, -10.0), _contact("2", 10.0, -8.0))
    )


def test_unparseable_source_pad_placement_fails_closed() -> None:
    board = _BOARD.read_text(encoding="utf-8").replace(
        '(layer "F.Cu") (at 5 5)', '(layer "F.Cu") (at 5 inf)', 1
    )

    with pytest.raises(UnsupportedFabricationFormat, match="malformed pad placement"):
        source_component_pads(board)
