"""Deterministic schematic-to-PCB footprint inventory comparisons."""

from __future__ import annotations

from typing import Literal, cast

from .model_primitives import Digest, RepositoryPath
from .models import NetlistContract
from .pcb_board_only_footprint_models import PcbBoardOnlyFootprintCoverage
from .pcb_board_only_footprints import board_only_pcb_footprints
from .pcb_component_inventory_models import (
    PcbComponentInventoryComparison,
    PcbComponentInventoryCoverageReport,
    PcbComponentValueMismatch,
    PcbFootprintIdentityMismatch,
    PcbMissingFootprintPlacement,
    PcbVariantPopulationCoverage,
)
from .pcb_component_population import compare_schematic_pcb_population
from .pcb_component_values import compare_schematic_pcb_values
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_pad_net_comparison import compare_schematic_pcb_pad_nets
from .pcb_pad_net_models import PcbSchematicBoardPadNetMismatch
from .pcb_required_fitted_reference_checks import (
    compare_required_fitted_references,
    required_fitted_reference_map_sha256,
)
from .pcb_required_fitted_reference_models import (
    PcbRequiredFittedReferenceCoverage,
    PcbRequiredFittedReferenceMap,
)
from .pcb_variant_population_capture import PcbVariantPopulationCapture


def compare_fitted_schematic_pcb_inventory(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> PcbComponentInventoryComparison:
    """Compare fitted schematic footprint assignments with native PCB placements."""
    if snapshot.schema_version not in {"12", "13", "14"}:
        raise ValueError(
            "PCB component inventory requires native footprint snapshot schema 12, 13, or 14"
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
    pad_net_mode: Literal["review", "block", "off"] = "off",
    board_only_mode: Literal["review", "block", "off"] = "off",
    required_fitted_reference_map: PcbRequiredFittedReferenceMap | None = None,
    required_fitted_reference_mode: Literal["review", "block", "off"] = "off",
    variant_population: PcbVariantPopulationCapture | None = None,
) -> PcbComponentInventoryCoverageReport:
    """Build complete inventory coverage or retain the precise comparison gap."""
    if all(
        item == "off"
        for item in (
            mode,
            value_mode,
            pad_net_mode,
            board_only_mode,
            required_fitted_reference_mode,
        )
    ):
        return PcbComponentInventoryCoverageReport(status="DISABLED", mode=mode)

    variant_coverage = (
        PcbVariantPopulationCoverage()
        if variant_population is None
        else variant_population.coverage
    )

    coverage_mode: Literal["review", "block", "off"] = cast(
        Literal["review", "block", "off"],
        next(
            (
                value
                for value in (
                    mode,
                    value_mode,
                    pad_net_mode,
                    board_only_mode,
                    required_fitted_reference_mode,
                )
                if value != "off"
            ),
            "off",
        ),
    )

    issue: str | None = None
    comparison = PcbComponentInventoryComparison()
    population_mismatches = ()
    value_mismatches: tuple[PcbComponentValueMismatch, ...] = ()
    value_comparison_status: Literal["NOT_APPLICABLE", "COMPLETE", "BLOCKED", "DISABLED"] = (
        "DISABLED" if value_mode == "off" else "BLOCKED"
    )
    value_comparison_issue: str | None = None
    pad_net_mismatches: tuple[PcbSchematicBoardPadNetMismatch, ...] = ()
    pad_net_comparison_status: Literal["NOT_APPLICABLE", "COMPLETE", "BLOCKED", "DISABLED"] = (
        "DISABLED" if pad_net_mode == "off" else "BLOCKED"
    )
    pad_net_comparison_issue: str | None = None
    board_only_coverage = (
        PcbBoardOnlyFootprintCoverage()
        if board_only_mode == "off"
        else PcbBoardOnlyFootprintCoverage(
            status="BLOCKED",
            mode=board_only_mode,
            issue="Board-only PCB footprint evidence is unavailable",
        )
    )
    required_map_sha256 = (
        None
        if required_fitted_reference_map is None
        else required_fitted_reference_map_sha256(required_fitted_reference_map)
    )
    required_fitted_coverage = (
        PcbRequiredFittedReferenceCoverage()
        if required_fitted_reference_mode == "off"
        else PcbRequiredFittedReferenceCoverage(
            status="BLOCKED",
            mode=required_fitted_reference_mode,
            map_sha256=required_map_sha256,
            issue=(
                "The enabled rule has no project-authored fitted-reference map"
                if required_fitted_reference_map is None
                else "Source-bound PCB inventory evidence is unavailable"
            ),
        )
    )
    if netlist is None:
        issue = "Source-bound native schematic netlist is unavailable"
    elif netlist_sha256 is None:
        issue = "Source-bound native schematic netlist digest is unavailable"
    elif snapshot.schema_version not in {"12", "13", "14"}:
        issue = "PCB component inventory needs native footprint snapshot schema 12, 13, or 14"
    else:
        try:
            comparison = compare_fitted_schematic_pcb_inventory(netlist, snapshot)
            if board_only_mode != "off":
                board_only_coverage = PcbBoardOnlyFootprintCoverage(
                    status="COMPLETE",
                    mode=board_only_mode,
                    footprints=board_only_pcb_footprints(netlist, snapshot),
                )
            if required_fitted_reference_mode != "off":
                if required_fitted_reference_map is None:
                    required_fitted_coverage = PcbRequiredFittedReferenceCoverage(
                        status="BLOCKED",
                        mode=required_fitted_reference_mode,
                        issue="The enabled rule has no project-authored fitted-reference map",
                    )
                else:
                    try:
                        mismatches = compare_required_fitted_references(
                            required_fitted_reference_map,
                            netlist,
                            snapshot,
                        )
                        required_fitted_coverage = PcbRequiredFittedReferenceCoverage(
                            status="COMPLETE",
                            mode=required_fitted_reference_mode,
                            map_sha256=required_map_sha256,
                            requirement_count=len(required_fitted_reference_map.requirements),
                            mismatches=mismatches,
                        )
                    except ValueError as exc:
                        required_fitted_coverage = PcbRequiredFittedReferenceCoverage(
                            status="BLOCKED",
                            mode=required_fitted_reference_mode,
                            map_sha256=required_map_sha256,
                            issue=str(exc),
                        )
            population_mismatches = compare_schematic_pcb_population(
                netlist,
                snapshot,
                variants=(
                    variant_population.sources
                    if variant_population is not None and variant_coverage.status == "COMPLETE"
                    else ()
                ),
            )
            if value_mode != "off":
                if snapshot.schema_version in {"13", "14"}:
                    value_mismatches = compare_schematic_pcb_values(netlist, snapshot)
                    value_comparison_status = "COMPLETE"
                else:
                    value_comparison_issue = "PCB component value comparison needs native footprint snapshot schema 13 or later"
        except ValueError as exc:
            issue = str(exc)

    if (
        value_mode != "off"
        and value_comparison_status == "BLOCKED"
        and value_comparison_issue is None
    ):
        value_comparison_issue = issue or "Source-bound PCB component value evidence is unavailable"

    if pad_net_mode != "off":
        if issue is not None:
            pad_net_comparison_issue = issue
        else:
            try:
                assert netlist is not None
                pad_net_mismatches = compare_schematic_pcb_pad_nets(netlist, snapshot)
                pad_net_comparison_status = "COMPLETE"
            except ValueError as exc:
                pad_net_comparison_issue = str(exc)

    if issue is not None:
        if board_only_mode != "off":
            board_only_coverage = PcbBoardOnlyFootprintCoverage(
                status="BLOCKED",
                mode=board_only_mode,
                issue=issue,
            )
        return PcbComponentInventoryCoverageReport(
            status="BLOCKED",
            mode=coverage_mode,
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
            pad_net_comparison_status=pad_net_comparison_status,
            pad_net_comparison_issue=pad_net_comparison_issue,
            board_only_footprint_coverage=board_only_coverage,
            required_fitted_reference_coverage=required_fitted_coverage,
            variant_population=variant_coverage,
            issue=issue,
        )

    if snapshot.schema_version not in {"12", "13", "14"}:
        raise ValueError(
            "PCB component inventory requires native footprint snapshot schema 12, 13, or 14"
        )
    return PcbComponentInventoryCoverageReport(
        status="COMPLETE",
        mode=coverage_mode,
        netlist_sha256=netlist_sha256,
        board_path=board_path,
        board_sha256=board_sha256,
        snapshot_path=snapshot_path,
        snapshot_sha256=snapshot_sha256,
        snapshot_schema=cast(Literal["12", "13", "14"], snapshot.schema_version),
        kicad_version=snapshot.kicad_version,
        image=snapshot.image,
        probe_sha256=probe_sha256,
        missing_placements=comparison.missing_placements,
        footprint_mismatches=comparison.footprint_mismatches,
        population_mismatches=population_mismatches,
        variant_population=variant_coverage,
        value_comparison_status=value_comparison_status,
        value_mismatches=value_mismatches,
        value_comparison_issue=value_comparison_issue,
        pad_net_comparison_status=pad_net_comparison_status,
        pad_net_mismatches=pad_net_mismatches,
        pad_net_comparison_issue=pad_net_comparison_issue,
        board_only_footprint_coverage=board_only_coverage,
        required_fitted_reference_coverage=required_fitted_coverage,
    )
