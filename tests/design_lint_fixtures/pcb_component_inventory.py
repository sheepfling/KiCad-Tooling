"""Shared synthetic input builders for PCB component-inventory checks."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbFootprintPlacementObservation,
)
from kicad_tooling.hwrepo.pcb_component_inventory import compare_fitted_schematic_pcb_inventory
from kicad_tooling.hwrepo.pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from kicad_tooling.hwrepo.pcb_component_population import compare_schematic_pcb_population

NETLIST_SHA256 = "a" * 64
BOARD_SHA256 = "b" * 64
SNAPSHOT_SHA256 = "c" * 64
PROBE_SHA256 = "d" * 64
IMAGE = "registry.example/kicad:10.0.5@sha256:" + "e" * 64
SnapshotSchema = Literal["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
ReviewMode = Literal["review", "block", "off"]


def netlist(
    *,
    components: dict[str, str] | None = None,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    assignments = components or {"U1": "Package_QFP:TQFP-48", "J1": "Connector:USB_B"}
    return NetlistContract(
        components={
            reference: ComponentContract(value="synthetic", footprint=footprint)
            for reference, footprint in assignments.items()
        },
        nets={},
        dnp_components=dnp,
    )


def snapshot(
    *references: str,
    schema_version: SnapshotSchema = "12",
    footprint_by_reference: dict[str, str] | None = None,
    dnp_by_reference: dict[str, bool] | None = None,
) -> PcbConnectivitySnapshot:
    identity_by_reference = {
        reference.casefold(): footprint
        for reference, footprint in (footprint_by_reference or {}).items()
    }
    dnp_by_key = {reference.casefold(): dnp for reference, dnp in (dnp_by_reference or {}).items()}
    return PcbConnectivitySnapshot(
        schema_version=schema_version,
        board_sha256=BOARD_SHA256,
        kicad_version="10.0.5",
        image=IMAGE,
        probe_sha256=PROBE_SHA256,
        zones_refilled=True,
        pads=(),
        net_ties=(),
        zones=(),
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(),
        copper_layers=("F.Cu", "B.Cu"),
        rule_areas=(),
        footprints=tuple(
            PcbFootprintPlacementObservation(
                reference=reference,
                footprint=identity_by_reference.get(reference.casefold(), "Synthetic:Footprint"),
                dnp=dnp_by_key.get(reference.casefold(), False),
                position_nm=(0, 0),
                orientation_microdegrees=0,
                side="F.Cu",
            )
            for reference in references
        ),
    )


def complete_report(
    observed: NetlistContract,
    board: PcbConnectivitySnapshot,
    *,
    mode: ReviewMode = "review",
) -> PcbComponentInventoryCoverageReport:
    comparison = compare_fitted_schematic_pcb_inventory(observed, board)
    return PcbComponentInventoryCoverageReport(
        status="COMPLETE",
        mode=mode,
        netlist_sha256=NETLIST_SHA256,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        snapshot_schema="12",
        kicad_version=board.kicad_version,
        image=board.image,
        probe_sha256=board.probe_sha256,
        missing_placements=comparison.missing_placements,
        footprint_mismatches=comparison.footprint_mismatches,
        population_mismatches=compare_schematic_pcb_population(observed, board),
    )


def coach(observed: NetlistContract) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-component-inventory",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
