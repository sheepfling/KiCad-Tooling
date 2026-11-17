"""One-to-one Excellon assignment across component pads and vias."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_contact_source import SourceComponentPad
from kicad_tooling.hwrepo.fabrication_drill_binding import require_excellon_source_drills
from kicad_tooling.hwrepo.fabrication_excellon import DrillHit, parse_excellon
from kicad_tooling.hwrepo.fabrication_via_binding import SourceVia

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def _pad(reference: str, *, x_nm: int = 10_000_000) -> SourceComponentPad:
    return SourceComponentPad(
        reference=reference,
        number="1",
        net_name="SIGNAL",
        contact_layer="through",
        x_nm=x_nm,
        y_nm=9_000_000,
        drill_nm=800_000,
        drill_plating="plated",
        drill_shape="circular",
        drill_width_nm=800_000,
        drill_height_nm=800_000,
    )


def _drills(*coordinates: str) -> tuple[DrillHit, ...]:
    hits = "\n".join(coordinates)
    return parse_excellon("M48\nMETRIC,LZ\nT1C0.800\n%\nG90\nG05\nT1\n" + hits + "\nM30\n")


def test_one_hit_cannot_satisfy_a_coincident_pad_and_via() -> None:
    pads = (_pad("J1"),)
    vias = (SourceVia("SIGNAL", 10_000_000, 9_000_000, 800_000),)

    with pytest.raises(UnsupportedFabricationFormat, match="cannot uniquely bind"):
        require_excellon_source_drills(pads, vias, _drills("X10.000Y-9.000"), ())


def test_coincident_pad_and_via_bind_to_distinct_duplicate_hits() -> None:
    pads = (_pad("J1"),)
    vias = (SourceVia("SIGNAL", 10_000_000, 9_000_000, 800_000),)

    require_excellon_source_drills(
        pads,
        vias,
        _drills("X10.000Y-9.000", "X10.000Y-9.000"),
        (),
    )


def test_unique_assignment_handles_overlapping_coordinate_tolerances() -> None:
    pads = (_pad("J1", x_nm=10_000_000), _pad("J2", x_nm=10_000_500))

    require_excellon_source_drills(
        pads,
        (),
        _drills("X10.000Y-9.000", "X10.001Y-9.000"),
        (),
    )
