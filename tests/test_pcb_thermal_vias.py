"""Authored thermal-pad via counts use exact native connectivity and geometry."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.pcb_thermal_vias import pcb_thermal_via_entries
from tests.pcb_thermal_vias_support import mapping, requirement, snapshot

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_disconnected_nearby_and_connected_out_of_radius_vias_do_not_count() -> None:
    evidence = snapshot(
        (
            (20_000, 0, "F.Cu", "In1.Cu", False),
            (500_000, 0, "F.Cu", "In1.Cu", True),
            (25_000, 0, "F.Cu", "B.Cu", True),
        )
    )

    (entry,) = pcb_thermal_via_entries(mapping(), evidence)

    assert entry.status == "INCOMPLETE"
    assert len(entry.measurements) == 3
    assert any("has 0 native-connected vias" in issue for issue in entry.issues)
    assert (
        sum(
            item.connected_to_pad_component
            and item.within_authored_radius
            and {item.start_layer.casefold(), item.end_layer.casefold()} == {"f.cu", "in1.cu"}
            for item in entry.measurements
        )
        == 0
    )


def test_local_connected_required_span_passes_and_nearby_open_via_is_excluded() -> None:
    evidence = snapshot(
        (
            (50_000, 0, "F.Cu", "In1.Cu", True),
            (10_000, 0, "F.Cu", "In1.Cu", False),
        )
    )

    (entry,) = pcb_thermal_via_entries(mapping(), evidence)

    assert entry.status == "COMPLETE"
    (measured_connected, measured_open) = entry.measurements
    assert measured_connected.connected_to_pad_component
    assert not measured_open.connected_to_pad_component


@pytest.mark.parametrize(
    ("pad_net", "footprint", "dnp"),
    (
        ("ALT_GND", "Synthetic:QFN", False),
        ("GND", "Synthetic:Other", False),
        ("GND", "Synthetic:QFN", True),
    ),
)
def test_identity_or_population_mismatch_is_incomplete(
    pad_net: str, footprint: str, dnp: bool
) -> None:
    (entry,) = pcb_thermal_via_entries(
        mapping(),
        snapshot(
            ((10_000, 0, "F.Cu", "In1.Cu", True),), pad_net=pad_net, footprint=footprint, dnp=dnp
        ),
    )

    assert entry.status == "INCOMPLETE"


def test_absent_pad_and_unavailable_copper_layer_are_incomplete() -> None:
    (absent,) = pcb_thermal_via_entries(mapping(), snapshot((), pad_present=False))
    (missing_layer,) = pcb_thermal_via_entries(mapping(), snapshot((), layers=("F.Cu", "B.Cu")))

    assert absent.status == "INCOMPLETE"
    assert "is absent" in absent.issues[0]
    assert missing_layer.status == "INCOMPLETE"
    assert any("absent from the native copper stack" in issue for issue in missing_layer.issues)


def test_radius_boundary_is_inclusive_and_reordering_is_deterministic() -> None:
    mapped = mapping(requirement(radius_um=100, minimum=2))
    evidence = snapshot(
        (
            (100_000, 0, "F.Cu", "In1.Cu", True),
            (0, 100_000, "In1.Cu", "F.Cu", True),
        )
    )
    reordered = evidence.model_copy(update={"vias": tuple(reversed(evidence.vias))})

    (first,) = pcb_thermal_via_entries(mapped, evidence)
    (second,) = pcb_thermal_via_entries(mapped, reordered)

    assert first.status == "COMPLETE"
    assert first.measurements == second.measurements


def test_authored_radius_change_changes_coverage() -> None:
    evidence = snapshot(((50_000, 0, "F.Cu", "In1.Cu", True),))
    (baseline,) = pcb_thermal_via_entries(mapping(requirement(radius_um=100)), evidence)
    (stricter,) = pcb_thermal_via_entries(mapping(requirement(radius_um=49)), evidence)

    assert baseline.status == "COMPLETE"
    assert stricter.status == "INCOMPLETE"
    assert baseline.measurements[0].center_distance_squared_nm2 == 50_000**2
    assert stricter.measurements[0].center_distance_squared_nm2 == 50_000**2
