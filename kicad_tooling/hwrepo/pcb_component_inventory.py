"""Deterministic schematic-to-PCB footprint inventory comparisons."""

from __future__ import annotations

from typing import Literal

from .model_primitives import Digest, RepositoryPath
from .models import NetlistContract
from .pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbMissingFootprintPlacement,
)
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot


def missing_fitted_footprint_placements(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbMissingFootprintPlacement, ...]:
    """Find fitted, footprint-assigned schematic parts absent from native PCB inventory."""
    if snapshot.schema_version != "12":
        raise ValueError("PCB component inventory requires native footprint snapshot schema 12")

    schematic_references: dict[str, str] = {}
    for reference in netlist.components:
        key = reference.casefold()
        if key in schematic_references:
            raise ValueError("Native netlist has duplicate case-insensitive component references")
        schematic_references[key] = reference

    board_references = {item.reference.casefold() for item in snapshot.footprints}
    dnp_references = {reference.casefold() for reference in netlist.dnp_components}
    missing = [
        PcbMissingFootprintPlacement(reference=reference, assigned_footprint=component.footprint)
        for reference, component in netlist.components.items()
        if component.footprint.strip()
        and reference.casefold() not in dnp_references
        and reference.casefold() not in board_references
    ]
    return tuple(sorted(missing, key=lambda item: item.reference.casefold()))


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
) -> PcbComponentInventoryCoverageReport:
    """Build complete inventory coverage or retain the precise comparison gap."""
    if mode == "off":
        return PcbComponentInventoryCoverageReport(status="DISABLED", mode=mode)

    issue: str | None = None
    missing: tuple[PcbMissingFootprintPlacement, ...] = ()
    if netlist is None:
        issue = "Source-bound native schematic netlist is unavailable"
    elif netlist_sha256 is None:
        issue = "Source-bound native schematic netlist digest is unavailable"
    elif snapshot.schema_version != "12":
        issue = "PCB component inventory needs native footprint snapshot schema 12"
    else:
        try:
            missing = missing_fitted_footprint_placements(netlist, snapshot)
        except ValueError as exc:
            issue = str(exc)

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
            issue=issue,
        )

    return PcbComponentInventoryCoverageReport(
        status="COMPLETE",
        mode=mode,
        netlist_sha256=netlist_sha256,
        board_path=board_path,
        board_sha256=board_sha256,
        snapshot_path=snapshot_path,
        snapshot_sha256=snapshot_sha256,
        snapshot_schema=snapshot.schema_version,
        kicad_version=snapshot.kicad_version,
        image=snapshot.image,
        probe_sha256=probe_sha256,
        missing_placements=missing,
    )
