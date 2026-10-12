"""Deterministic schematic-to-PCB footprint inventory comparisons."""

from __future__ import annotations

from typing import Literal, cast

from .model_primitives import Digest, RepositoryPath
from .models import NetlistContract
from .pcb_component_inventory_models import (
    PcbComponentInventoryComparison,
    PcbComponentInventoryCoverageReport,
    PcbComponentValueMismatch,
    PcbFootprintIdentityMismatch,
    PcbMissingFootprintPlacement,
)
from .pcb_component_population import compare_schematic_pcb_population
from .pcb_component_values import compare_schematic_pcb_values
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot


def compare_fitted_schematic_pcb_inventory(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> PcbComponentInventoryComparison:
    """Compare fitted schematic footprint assignments with native PCB placements."""
    if snapshot.schema_version not in {"12", "13"}:
        raise ValueError(
            "PCB component inventory requires native footprint snapshot schema 12 or 13"
        )

    schematic_references: dict[str, str] = {}
    for reference in netlist.components:
        key = reference.casefold()
        if key in schematic_references:
            raise ValueError("Native netlist has duplicate case-insensitive component references")
        schematic_references[key] = reference

    board_footprints: dict[str, str] = {}
    for item in snapshot.footprints:
        key = item.reference.casefold()
        if key in board_footprints:
            raise ValueError("Native PCB has duplicate case-insensitive footprint references")
        board_footprints[key] = item.footprint

    dnp_references = {reference.casefold() for reference in netlist.dnp_components}
    missing: list[PcbMissingFootprintPlacement] = []
    mismatches: list[PcbFootprintIdentityMismatch] = []
    for reference, component in netlist.components.items():
        assigned_footprint = component.footprint.strip()
        key = reference.casefold()
        if not assigned_footprint or key in dnp_references:
            continue
        placed = board_footprints.get(key)
        if placed is None:
            missing.append(
                PcbMissingFootprintPlacement(
                    reference=reference,
                    assigned_footprint=assigned_footprint,
                )
            )
        elif assigned_footprint != placed.strip():
            mismatches.append(
                PcbFootprintIdentityMismatch(
                    reference=reference,
                    assigned_footprint=assigned_footprint,
                    placed_footprint=placed,
                )
            )

    return PcbComponentInventoryComparison(
        missing_placements=tuple(sorted(missing, key=lambda item: item.reference.casefold())),
        footprint_mismatches=tuple(sorted(mismatches, key=lambda item: item.reference.casefold())),
    )


def missing_fitted_footprint_placements(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbMissingFootprintPlacement, ...]:
    """Compatibility view of fitted schematic parts absent from native PCB inventory."""
    return compare_fitted_schematic_pcb_inventory(netlist, snapshot).missing_placements


def evaluate_native_component_inventory_coverage(
    netlist: NetlistContract | None,
    snapshot: PcbConnectivitySnapshot,
    *,
    mode: Literal["review", "block", "off"],
    netlist_sha256: Digest | None,
    board_path: RepositoryPath,
    board_sha256: Digest,
    snapshot_path: RepositoryPath,
    snapshot_sha256: Digest,
    probe_sha256: Digest,
    value_mode: Literal["review", "block", "off"] = "off",
) -> PcbComponentInventoryCoverageReport:
    """Build complete inventory coverage or retain the precise comparison gap."""
    if mode == "off":
        return PcbComponentInventoryCoverageReport(status="DISABLED", mode=mode)

    issue: str | None = None
    comparison = PcbComponentInventoryComparison()
    population_mismatches = ()
    value_mismatches: tuple[PcbComponentValueMismatch, ...] = ()
    value_comparison_status: Literal["NOT_APPLICABLE", "COMPLETE", "BLOCKED", "DISABLED"] = (
        "DISABLED" if value_mode == "off" else "BLOCKED"
    )
    value_comparison_issue: str | None = None
    if netlist is None:
        issue = "Source-bound native schematic netlist is unavailable"
    elif netlist_sha256 is None:
        issue = "Source-bound native schematic netlist digest is unavailable"
    elif snapshot.schema_version not in {"12", "13"}:
        issue = "PCB component inventory needs native footprint snapshot schema 12 or 13"
    else:
        try:
            comparison = compare_fitted_schematic_pcb_inventory(netlist, snapshot)
            population_mismatches = compare_schematic_pcb_population(netlist, snapshot)
            if value_mode != "off":
                if snapshot.schema_version == "13":
                    value_mismatches = compare_schematic_pcb_values(netlist, snapshot)
                    value_comparison_status = "COMPLETE"
                else:
                    value_comparison_issue = (
                        "PCB component value comparison needs native footprint snapshot schema 13"
                    )
        except ValueError as exc:
            issue = str(exc)

    if (
        value_mode != "off"
        and value_comparison_status == "BLOCKED"
        and value_comparison_issue is None
    ):
        value_comparison_issue = issue or "Source-bound PCB component value evidence is unavailable"

    if issue is not None:
        return PcbComponentInventoryCoverageReport(
            status="BLOCKED",
            mode=mode,
            netlist_sha256=netlist_sha256,
            board_path=board_path,
            board_sha256=board_sha256,
            snapshot_path=snapshot_path,
            snapshot_sha256=snapshot_sha256,
            kicad_version=snapshot.kicad_version,
            image=snapshot.image,
            probe_sha256=probe_sha256,
            value_comparison_status=value_comparison_status,
            value_comparison_issue=value_comparison_issue,
            issue=issue,
        )

    if snapshot.schema_version not in {"12", "13"}:
        raise ValueError(
            "PCB component inventory requires native footprint snapshot schema 12 or 13"
        )
    return PcbComponentInventoryCoverageReport(
        status="COMPLETE",
        mode=mode,
        netlist_sha256=netlist_sha256,
        board_path=board_path,
        board_sha256=board_sha256,
        snapshot_path=snapshot_path,
        snapshot_sha256=snapshot_sha256,
        snapshot_schema=cast(Literal["12", "13"], snapshot.schema_version),
        kicad_version=snapshot.kicad_version,
        image=snapshot.image,
        probe_sha256=probe_sha256,
        missing_placements=comparison.missing_placements,
        footprint_mismatches=comparison.footprint_mismatches,
        population_mismatches=population_mismatches,
        value_comparison_status=value_comparison_status,
        value_mismatches=value_mismatches,
        value_comparison_issue=value_comparison_issue,
    )
