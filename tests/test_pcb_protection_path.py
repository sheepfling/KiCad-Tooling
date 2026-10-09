"""Synthetic regressions for the project-mapped PCB protection-path screen."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    PcbProtectionPathCoverageReport,
    PcbProtectionPathMap,
    PcbProtectionPathRequirement,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_protection_path import pcb_protection_path_entries

CONNECTOR = "Synthetic:Conn_2"
PROTECTION = "Synthetic:TVS_2"
RULE = "pcb.protection_entry_path"


def requirement(
    *,
    max_entry_distance_um: int | None = 100,
    minimum_reference_vias: int | None = 2,
    reference_via_radius_um: int | None = 3_000,
) -> PcbProtectionPathRequirement:
    return PcbProtectionPathRequirement(
        id="usb-d-plus-entry",
        connector_reference="J1",
        connector_footprint=CONNECTOR,
        connector_signal_pad="J1.1",
        protection_reference="D1",
        protection_footprint=PROTECTION,
        protection_signal_pad="D1.1",
        protection_reference_pad="D1.2",
        signal_net="USB_D_P",
        reference_net="ESD_RETURN",
        max_entry_distance_um=max_entry_distance_um,
        minimum_reference_vias=minimum_reference_vias,
        reference_via_radius_um=reference_via_radius_um,
    )


def mapping(*item: PcbProtectionPathRequirement) -> PcbProtectionPathMap:
    return PcbProtectionPathMap(
        basis="Synthetic project-reviewed external protection pad map",
        requirements=item or (requirement(),),
    )


def snapshot(
    *,
    entry_distance_nm: int = 100_000,
    via_offsets_nm: tuple[int, ...] = (2_900_000, 3_000_000),
    unconnected_via_offsets_nm: tuple[int, ...] = (),
    signal_connected: bool = True,
    wrong_nets: frozenset[str] = frozenset(),
    dnp: frozenset[str] = frozenset(),
    wrong_footprints: frozenset[str] = frozenset(),
) -> PcbConnectivitySnapshot:
    base_x_nm = entry_distance_nm
    coordinates = {
        "J1.1": (0, 0),
        "D1.1": (base_x_nm, 0),
        "D1.2": (base_x_nm, 20_000),
    }
    via_ids = tuple(
        hashlib.sha256(f"synthetic-esd-via-{index}".encode()).hexdigest()
        for index, _ in enumerate(via_offsets_nm)
    )
    vias = tuple(
        PcbViaObservation(
            id=via_id,
            net="ESD_RETURN",
            x_nm=base_x_nm + offset,
            y_nm=20_000,
            start_layer="F.Cu",
            end_layer="In1.Cu",
            diameter_nm=600_000,
            drill_nm=300_000,
            kind="through",
            multiplicity=1,
        )
        for via_id, offset in zip(via_ids, via_offsets_nm, strict=True)
    )
    vias += tuple(
        PcbViaObservation(
            id=hashlib.sha256(f"synthetic-unconnected-esd-via-{index}".encode()).hexdigest(),
            net="ESD_RETURN",
            x_nm=base_x_nm + offset,
            y_nm=20_000,
            start_layer="F.Cu",
            end_layer="In1.Cu",
            diameter_nm=600_000,
            drill_nm=300_000,
            kind="through",
            multiplicity=1,
        )
        for index, offset in enumerate(unconnected_via_offsets_nm)
    )
    signal_component = ("J1.1", "D1.1") if signal_connected else ("J1.1",)
    rows = []
    for pad_ref in ("J1.1", "D1.1", "D1.2"):
        component, _pad_number = pad_ref.split(".")
        net = "ESD_RETURN" if pad_ref == "D1.2" else "USB_D_P"
        if pad_ref in wrong_nets:
            net = "OTHER_NET"
        peers = signal_component if pad_ref in signal_component else (pad_ref,)
        rows.append(
            PcbPadConnectivityObservation(
                pad=pad_ref,
                net=net,
                footprint=(
                    "Synthetic:WrongFootprint"
                    if component in wrong_footprints
                    else CONNECTOR
                    if component == "J1"
                    else PROTECTION
                ),
                dnp=component in dnp,
                connected_pads=tuple(dict.fromkeys((pad_ref, *peers))),
                connected_zones=(),
                connected_islands=(),
                connected_vias=via_ids if pad_ref == "D1.2" else (),
                positions_nm=(coordinates[pad_ref],),
            )
        )
    return PcbConnectivitySnapshot(
        schema_version="5",
        board_sha256="a" * 64,
        kicad_version="10.0.5",
        image="ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=tuple(rows),
        net_ties=(),
        zones=(),
        vias=vias,
        access_probe_observations=(),
        access_probe_requests_sha256=None,
    )


def coverage_report(
    mapped: PcbProtectionPathMap,
    evidence: PcbConnectivitySnapshot,
) -> PcbProtectionPathCoverageReport:
    entries = pcb_protection_path_entries(mapped, evidence)
    return PcbProtectionPathCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=hashlib.sha256(mapped.model_dump_json().encode()).hexdigest(),
        board_path="projects/synthetic/project.kicad_pcb",
        board_sha256=evidence.board_sha256,
        snapshot_path="build/design-lint/pcb-protection-path/snapshot.json",
        snapshot_sha256=hashlib.sha256(evidence.model_dump_json().encode()).hexdigest(),
        probe_sha256=evidence.probe_sha256,
        kicad_version=evidence.kicad_version,
        image=evidence.image,
        netlist_sha256="f" * 64,
        entries=entries,
    )


def test_project_authored_boundaries_accept_exact_entry_and_via_limits() -> None:
    entries = pcb_protection_path_entries(mapping(), snapshot())

    assert entries[0].status == "COMPLETE"
    assert entries[0].connector_to_protection_distance_nm == 100_000
    assert entries[0].connected_reference_via_count == 2
    assert entries[0].reference_vias_within_radius == 2
    assert entries[0].nearest_reference_via_distance_nm == 2_900_000


def test_distance_and_via_count_faults_are_causal_and_reviewable() -> None:
    far = pcb_protection_path_entries(mapping(), snapshot(entry_distance_nm=100_001))[0]
    one_near_via = pcb_protection_path_entries(
        mapping(), snapshot(via_offsets_nm=(2_900_000, 3_000_001))
    )[0]

    assert far.status == "INCOMPLETE"
    assert far.connector_to_protection_distance_nm == 100_001
    assert any("project limit is 100 um" in item for item in far.issues)
    assert one_near_via.reference_vias_within_radius == 1
    assert any("minimum is 2" in item for item in one_near_via.issues)


def test_near_unconnected_via_does_not_satisfy_reference_via_requirement() -> None:
    evidence = snapshot(via_offsets_nm=(), unconnected_via_offsets_nm=(10_000,))
    entry = pcb_protection_path_entries(mapping(), evidence)[0]

    assert entry.status == "INCOMPLETE"
    assert entry.connected_reference_via_count == 0
    assert entry.reference_vias_within_radius == 0
    assert any("no native-connected via" in item for item in entry.issues)


def test_net_identity_footprint_dnp_and_copper_disconnection_are_reported() -> None:
    evidence = snapshot(
        signal_connected=False,
        wrong_nets=frozenset({"J1.1", "D1.1"}),
        dnp=frozenset({"D1"}),
        wrong_footprints=frozenset({"J1"}),
    )
    entry = pcb_protection_path_entries(mapping(), evidence)[0]

    assert entry.status == "INCOMPLETE"
    assert any("footprint" in item for item in entry.issues)
    assert any("do-not-populate" in item for item in entry.issues)
    assert any("expected 'USB_D_P'" in item for item in entry.issues)
    assert any("Native copper path" in item for item in entry.issues)


def test_legacy_snapshot_without_connected_via_inventory_is_incomplete() -> None:
    data = snapshot().model_dump(mode="python")
    data["schema_version"] = "2"
    data.pop("vias")
    for pad in data["pads"]:
        pad.pop("connected_vias")
    legacy = PcbConnectivitySnapshot.model_validate(data)

    entry = pcb_protection_path_entries(mapping(), legacy)[0]

    assert entry.status == "INCOMPLETE"
    assert any("evidence" in item for item in entry.issues)
    assert not any("no native-connected via" in item for item in entry.issues)


def test_pad_and_via_inventory_order_does_not_change_results() -> None:
    spec = mapping()
    original = snapshot()
    reordered = original.model_copy(
        update={"pads": tuple(reversed(original.pads)), "vias": tuple(reversed(original.vias))}
    )

    assert pcb_protection_path_entries(spec, original) == pcb_protection_path_entries(
        spec, reordered
    )
    repaired = pcb_protection_path_entries(
        spec,
        snapshot(entry_distance_nm=100_000, via_offsets_nm=(2_900_000, 3_000_000)),
    )[0]
    fault = pcb_protection_path_entries(
        spec,
        snapshot(entry_distance_nm=100_001, via_offsets_nm=(2_900_000, 3_000_001)),
    )[0]
    assert repaired.status == "COMPLETE"
    assert fault.status == "INCOMPLETE"


def test_map_requires_exact_pad_ownership_and_paired_via_limits() -> None:
    invalid = requirement().model_dump()
    invalid["connector_signal_pad"] = "J2.1"
    with pytest.raises(ValidationError, match="belong to its connector"):
        PcbProtectionPathRequirement.model_validate(invalid)
    with pytest.raises(ValidationError):
        PcbProtectionPathRequirement(
            **{
                **requirement().model_dump(),
                "minimum_reference_vias": None,
            }
        )


def test_design_lint_emits_configurable_review_finding_for_fault() -> None:
    spec = mapping()
    evidence = snapshot(entry_distance_nm=100_001, via_offsets_nm=(2_900_000,))
    measured = coverage_report(spec, evidence)
    native = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-protection",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256="f" * 64,
    )

    report = evaluate(
        "synthetic-protection",
        native,
        DesignLintPolicy(pcb_protection_path_map=spec),
        pcb_protection_path_coverage=measured,
    )

    finding = next(item for item in report.findings if item.rule_id == RULE)
    assert report.status == "REVIEW"
    assert report.pcb_protection_path.status == "INCOMPLETE"
    assert finding.mode == "review"
    assert finding.evidence["connector_to_protection_pad_center_distance"] == ("100001 nm",)
