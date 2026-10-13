"""Shared synthetic input builders for PCB component-inventory checks."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
)
from kicad_tooling.hwrepo.pcb_component_inventory import compare_fitted_schematic_pcb_inventory
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)
from kicad_tooling.hwrepo.pcb_component_population import compare_schematic_pcb_population
from kicad_tooling.hwrepo.pcb_component_values import compare_schematic_pcb_values

NETLIST_SHA256 = "a" * 64
BOARD_SHA256 = "b" * 64
SNAPSHOT_SHA256 = "c" * 64
PROBE_SHA256 = "d" * 64
IMAGE = "registry.example/kicad:10.0.5@sha256:" + "e" * 64
SnapshotSchema = Literal["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14"]
ReviewMode = Literal["review", "block", "off"]


def netlist(
    *,
    components: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    dnp: tuple[str, ...] = (),
    nets: dict[str, tuple[str, ...]] | None = None,
    unconnected_nets: dict[str, tuple[str, ...]] | None = None,
    component_pin_numbers: dict[str, tuple[str, ...]] | None = None,
) -> NetlistContract:
    assignments = components or {"U1": "Package_QFP:TQFP-48", "J1": "Connector:USB_B"}
    return NetlistContract(
        components={
            reference: ComponentContract(
                value=(values or {}).get(reference, "synthetic"),
                footprint=footprint,
            )
            for reference, footprint in assignments.items()
        },
        nets=nets or {},
        unconnected_nets=unconnected_nets or {},
        dnp_components=dnp,
        component_pin_numbers=component_pin_numbers or {},
    )


def snapshot(
    *references: str,
    schema_version: SnapshotSchema = "12",
    footprint_by_reference: dict[str, str] | None = None,
    dnp_by_reference: dict[str, bool] | None = None,
    value_by_reference: dict[str, str] | None = None,
    pad_net_by_reference: dict[str, str | None] | None = None,
) -> PcbConnectivitySnapshot:
    identity_by_reference = {
        reference.casefold(): footprint
        for reference, footprint in (footprint_by_reference or {}).items()
    }
    dnp_by_key = {reference.casefold(): dnp for reference, dnp in (dnp_by_reference or {}).items()}
    value_by_key = {
        reference.casefold(): value for reference, value in (value_by_reference or {}).items()
    }
    pad_net_values = pad_net_by_reference or {}
    return PcbConnectivitySnapshot(
        schema_version=schema_version,
        board_sha256=BOARD_SHA256,
        kicad_version="10.0.5",
        image=IMAGE,
        probe_sha256=PROBE_SHA256,
        zones_refilled=True,
        pads=tuple(
            PcbPadConnectivityObservation(
                pad=pad_reference,
                net=net_name,
                footprint=identity_by_reference.get(
                    pad_reference.rsplit(".", 1)[0].casefold(), "Synthetic:Footprint"
                ),
                dnp=dnp_by_key.get(pad_reference.rsplit(".", 1)[0].casefold(), False),
                connected_pads=(pad_reference,),
                connected_zones=(),
                connected_islands=(),
                connected_vias=(),
                positions_nm=((0, 0),),
            )
            for pad_reference, net_name in pad_net_values.items()
        ),
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
                value=(
                    value_by_key.get(reference.casefold(), "synthetic")
                    if schema_version in {"13", "14"}
                    else None
                ),
                position_nm=(0, 0),
                orientation_microdegrees=0,
                side="F.Cu",
            )
            for reference in references
        ),
        touch_pad_clearance_observations=(),
        touch_pad_clearance_requests_sha256=None,
    )


def complete_report(
    observed: NetlistContract,
    board: PcbConnectivitySnapshot,
    *,
    mode: ReviewMode = "review",
    value_mode: ReviewMode = "off",
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
        snapshot_schema=(
            board.schema_version if board.schema_version in {"12", "13", "14"} else "12"
        ),
        kicad_version=board.kicad_version,
        image=board.image,
        probe_sha256=board.probe_sha256,
        missing_placements=comparison.missing_placements,
        footprint_mismatches=comparison.footprint_mismatches,
        population_mismatches=compare_schematic_pcb_population(observed, board),
        value_comparison_status=(
            "DISABLED"
            if value_mode == "off"
            else "COMPLETE"
            if board.schema_version in {"13", "14"}
            else "BLOCKED"
        ),
        value_mismatches=(
            compare_schematic_pcb_values(observed, board)
            if value_mode != "off" and board.schema_version in {"13", "14"}
            else ()
        ),
        value_comparison_issue=(
            "PCB component value comparison needs native footprint snapshot schema 13 or later"
            if value_mode != "off" and board.schema_version not in {"13", "14"}
            else None
        ),
    )


def coach(observed: NetlistContract) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-component-inventory",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
