"""Synthetic return-via evidence regressions for PCB decoupling requirements."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import PcbConnectivitySnapshot, PcbDecouplingCapacitor
from kicad_tooling.hwrepo.pcb_decoupling import pcb_decoupling_entries
from tests.pcb_decoupling_support import CAP, mapping, requirement, snapshot

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.return_path_lint]


def test_legacy_snapshot_without_connected_via_inventory_is_incomplete() -> None:
    current = snapshot(distances_nm={"C1": 80000})
    legacy_data = current.model_dump(mode="python")
    legacy_data["schema_version"] = "2"
    legacy_data.pop("vias")
    for pad in legacy_data["pads"]:
        pad.pop("connected_vias")
    legacy = PcbConnectivitySnapshot.model_validate(legacy_data)
    entry = pcb_decoupling_entries(
        mapping(requirement(maximum_um=100, maximum_return_via_um=40)), legacy
    )[0]
    assert entry.status == "INCOMPLETE"
    assert "native connected-via evidence" in " ".join(entry.candidates[0].issues).casefold()
    assert "no native-connected via" not in " ".join(entry.candidates[0].issues)


def test_native_connected_return_via_at_inclusive_authored_boundary_passes() -> None:
    evidence = snapshot(
        distances_nm={"C1": 80000}, return_vias_nm={"C1": ((120000, 20000), (200000, 20000))}
    )
    entries = pcb_decoupling_entries(
        mapping(requirement(maximum_um=None, maximum_return_via_um=40)), evidence
    )
    assert entries[0].status == "COMPLETE"
    assert entries[0].selected_capacitors == ("C1",)
    candidate = entries[0].candidates[0]
    assert candidate.connected_return_via_count == 2
    assert candidate.return_via_distance_nm == 40000
    assert (
        candidate.nearest_return_via_id
        == next(item for item in evidence.pads if item.pad == "C1.2").connected_vias[0]
    )
    assert "No project IC-to-cap distance threshold" in entries[0].issues[0]


def test_distant_or_absent_connected_return_via_does_not_satisfy_map() -> None:
    spec = mapping(requirement(maximum_um=100, maximum_return_via_um=40))
    distant = pcb_decoupling_entries(
        spec, snapshot(distances_nm={"C1": 80000}, return_vias_nm={"C1": ((120001, 20000),)})
    )[0]
    absent = pcb_decoupling_entries(
        spec, snapshot(distances_nm={"C1": 80000}, unconnected_vias_nm=((80000, 20000),))
    )[0]
    assert distant.status == "INCOMPLETE"
    assert distant.selected_capacitors == ()
    assert distant.candidates[0].return_via_distance_nm == 40001
    assert "the project limit is 40 um" in " ".join(distant.candidates[0].issues)
    assert absent.status == "INCOMPLETE"
    assert absent.candidates[0].connected_return_via_count == 0
    assert "no native-connected via" in " ".join(absent.candidates[0].issues)


def test_supply_distance_and_return_via_must_belong_to_same_selected_capacitor() -> None:
    capacitors = (
        PcbDecouplingCapacitor(reference="C1", footprint=CAP, supply_pad="C1.1", return_pad="C1.2"),
        PcbDecouplingCapacitor(reference="C2", footprint=CAP, supply_pad="C2.1", return_pad="C2.2"),
    )
    entry = pcb_decoupling_entries(
        mapping(
            requirement(
                capacitors=capacitors, maximum_um=100, maximum_return_via_um=40, selection="any"
            )
        ),
        snapshot(
            distances_nm={"C1": 80000, "C2": 500000}, return_vias_nm={"C2": ((540000, 20000),)}
        ),
    )[0]
    assert entry.status == "INCOMPLETE"
    assert entry.selected_capacitors == ()
    assert entry.candidates[0].distance_nm == 80000
    assert entry.candidates[0].return_via_distance_nm is None
    assert entry.candidates[1].return_via_distance_nm == 40000


def test_return_via_order_is_stable_and_moving_it_past_limit_clears_candidate() -> None:
    spec = mapping(requirement(maximum_um=100, maximum_return_via_um=40))
    connected = snapshot(
        distances_nm={"C1": 80000}, return_vias_nm={"C1": ((120000, 20000), (100000, 20000))}
    )
    reordered = connected.model_copy(
        update={
            "vias": tuple(reversed(connected.vias)),
            "pads": tuple(
                item.model_copy(update={"connected_vias": tuple(reversed(item.connected_vias))})
                for item in reversed(connected.pads)
            ),
        }
    )
    fault = snapshot(distances_nm={"C1": 80000}, return_vias_nm={"C1": ((120001, 20000),)})
    passing_entry = pcb_decoupling_entries(spec, connected)[0]
    reordered_entry = pcb_decoupling_entries(spec, reordered)[0]
    fault_entry = pcb_decoupling_entries(spec, fault)[0]
    assert passing_entry == reordered_entry
    assert passing_entry.selected_capacitors == ("C1",)
    assert fault_entry.status == "INCOMPLETE"
    assert fault_entry.selected_capacitors == ()
