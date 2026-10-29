"""Review prompts for project-required PCB references that are not fitted."""

from __future__ import annotations

from .design_lint_types import Candidate
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_required_fitted_reference_models import (
    PcbRequiredFittedReferenceCoverage,
    PcbRequiredFittedReferenceMismatch,
)

RULE_ID = "pcb.required_fitted_reference"


def pcb_required_fitted_reference_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate explicit fitted-reference requirements into exact review findings."""
    if report is None:
        return ()
    coverage = report.required_fitted_reference_coverage
    if coverage.status == "DISABLED":
        return ()
    if coverage.status == "BLOCKED":
        return (
            Candidate(
                rule_id=RULE_ID,
                subject="project-required fitted-reference comparison unavailable",
                message=(
                    "The configured fitted-reference requirement could not be checked against "
                    "source-bound native schematic and PCB evidence. No conclusion is available."
                ),
                evidence={
                    "coverage_issue": (coverage.issue or "unavailable",),
                    "requirement_map_sha256": (
                        () if coverage.map_sha256 is None else (coverage.map_sha256,)
                    ),
                    "netlist_sha256": (
                        () if report.netlist_sha256 is None else (report.netlist_sha256,)
                    ),
                    "board_path": (() if report.board_path is None else (report.board_path,)),
                    "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
                    "snapshot_sha256": (
                        () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
                    ),
                },
            ),
        )

    return tuple(
        Candidate(
            rule_id=RULE_ID,
            subject=(
                f"{item.reference}: required fitted component does not match source"
                if item.variant is None
                else f"{item.reference} in variant '{item.variant}': required fitted component does not match source"
            ),
            message=(
                "The project explicitly requires this reference to be fitted with the declared "
                "identity. Review the listed schematic and PCB differences, then correct the "
                "sources or update the independently approved requirement. This check does not "
                "infer assembly intent from similar components."
            ),
            evidence=_candidate_evidence(report, coverage, item),
        )
        for item in coverage.mismatches
    )


def _candidate_evidence(
    report: PcbComponentInventoryCoverageReport,
    coverage: PcbRequiredFittedReferenceCoverage,
    item: PcbRequiredFittedReferenceMismatch,
) -> dict[str, tuple[str, ...]]:
    evidence: dict[str, tuple[str, ...]] = {
        "reference": (item.reference,),
        "basis": (item.basis,),
        "violations": item.violations,
        "expected_footprint": (item.expected_footprint,),
        "schematic_footprint": (
            () if item.schematic_footprint is None else (item.schematic_footprint,)
        ),
        "board_footprint": (() if item.board_footprint is None else (item.board_footprint,)),
        "expected_symbol": (() if item.expected_symbol is None else (item.expected_symbol,)),
        "observed_symbol": (() if item.observed_symbol is None else (item.observed_symbol,)),
        "expected_part_id": (() if item.expected_part_id is None else (item.expected_part_id,)),
        "observed_part_id": (() if item.observed_part_id is None else (item.observed_part_id,)),
        "schematic_dnp": (() if item.schematic_dnp is None else (str(item.schematic_dnp).lower(),)),
        "board_dnp": (() if item.board_dnp is None else (str(item.board_dnp).lower(),)),
        "requirement_map_sha256": (coverage.map_sha256 or "unavailable",),
        "netlist_sha256": (report.netlist_sha256 or "unavailable",),
        "board_path": (report.board_path or "unavailable",),
        "board_sha256": (report.board_sha256 or "unavailable",),
        "snapshot_sha256": (report.snapshot_sha256 or "unavailable",),
        "snapshot_schema": (report.snapshot_schema or "unavailable",),
        "kicad_version": (report.kicad_version or "unavailable",),
        "image": (report.image or "unavailable",),
        "probe_sha256": (report.probe_sha256 or "unavailable",),
    }
    if item.variant is not None:
        evidence["variant"] = (item.variant,)
        evidence["variant_evidence"] = _variant_evidence(report, item.variant)
    return evidence


def _variant_evidence(
    report: PcbComponentInventoryCoverageReport,
    variant: str | None,
) -> tuple[str, ...]:
    if variant is None:
        return ()
    evidence = next(
        (
            item
            for item in report.variant_population.evidence
            if item.variant.casefold() == variant.casefold()
        ),
        None,
    )
    if evidence is None:
        return (f"{variant}: unavailable",)
    return (
        f"tool={report.variant_population.kicad_version}@{report.variant_population.image}",
        f"project={report.variant_population.project_path}@{report.variant_population.project_sha256}",
        f"schematic={report.variant_population.schematic_path}@{report.variant_population.schematic_sha256}",
        f"board={report.variant_population.board_path}@{report.variant_population.board_sha256}",
        f"variant_probe={report.variant_population.board_variant_probe_path}@{report.variant_population.board_variant_probe_sha256}",
        f"variant_request={report.variant_population.board_variant_request_path}@{report.variant_population.board_variant_request_sha256}",
        f"variant_probe_command={report.variant_population.board_variant_command_path}@{report.variant_population.board_variant_command_sha256}",
        f"{evidence.variant}:netlist={evidence.netlist_path}@{evidence.netlist_sha256}",
        f"{evidence.variant}:netlist_command={evidence.netlist_command_path}@{evidence.netlist_command_sha256}",
        f"{evidence.variant}:board_all={evidence.board_all_positions_path}@{evidence.board_all_positions_sha256}",
        f"{evidence.variant}:board_all_command={evidence.board_all_command_path}@{evidence.board_all_command_sha256}",
        f"{evidence.variant}:board_fitted={evidence.board_fitted_positions_path}@{evidence.board_fitted_positions_sha256}",
        f"{evidence.variant}:board_fitted_command={evidence.board_fitted_command_path}@{evidence.board_fitted_command_sha256}",
    )
