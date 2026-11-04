"""Typed evidence and wire projection for project-required fitted references."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentInventorySourceReceipt,
    PcbVariantPopulationCoverage,
)
from .pcb_required_fitted_reference_models import (
    PcbRequiredFittedReferenceCoverage,
    PcbRequiredFittedReferenceMismatch,
)

RULE_ID: DesignLintRuleId = "pcb.required_fitted_reference"


@dataclass(frozen=True, slots=True)
class PcbRequiredFittedReferenceEvidence:
    """One authored fitted-reference mismatch and all evidence used to compare it."""

    observation: PcbRequiredFittedReferenceMismatch
    coverage: PcbRequiredFittedReferenceCoverage
    receipt: PcbComponentInventorySourceReceipt
    variant_population: PcbVariantPopulationCoverage


def project_pcb_required_fitted_reference_evidence(
    source: PcbRequiredFittedReferenceEvidence,
) -> CandidateEvidenceProjection:
    """Project typed requirement, observation, and native evidence to report fields."""
    item = source.observation
    coverage = source.coverage
    receipt = source.receipt
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
        "netlist_sha256": (receipt.netlist_sha256 or "unavailable",),
        "board_path": (receipt.board_path or "unavailable",),
        "board_sha256": (receipt.board_sha256 or "unavailable",),
        "snapshot_sha256": (receipt.snapshot_sha256 or "unavailable",),
        "snapshot_schema": (receipt.snapshot_schema or "unavailable",),
        "kicad_version": (receipt.kicad_version or "unavailable",),
        "image": (receipt.image or "unavailable",),
        "probe_sha256": (receipt.probe_sha256 or "unavailable",),
    }
    if item.variant is not None:
        evidence["variant"] = (item.variant,)
        evidence["variant_evidence"] = _variant_evidence(
            source.variant_population,
            item.variant,
        )
    return CandidateEvidenceProjection(rule_id=RULE_ID, evidence=evidence)


def _variant_evidence(
    coverage: PcbVariantPopulationCoverage,
    variant: str,
) -> tuple[str, ...]:
    evidence = next(
        (item for item in coverage.evidence if item.variant.casefold() == variant.casefold()),
        None,
    )
    if evidence is None:
        return (f"{variant}: unavailable",)
    return (
        f"tool={coverage.kicad_version}@{coverage.image}",
        f"project={coverage.project_path}@{coverage.project_sha256}",
        f"schematic={coverage.schematic_path}@{coverage.schematic_sha256}",
        f"board={coverage.board_path}@{coverage.board_sha256}",
        f"variant_probe={coverage.board_variant_probe_path}@{coverage.board_variant_probe_sha256}",
        f"variant_request={coverage.board_variant_request_path}@{coverage.board_variant_request_sha256}",
        f"variant_probe_command={coverage.board_variant_command_path}@{coverage.board_variant_command_sha256}",
        f"{evidence.variant}:netlist={evidence.netlist_path}@{evidence.netlist_sha256}",
        f"{evidence.variant}:netlist_command={evidence.netlist_command_path}@{evidence.netlist_command_sha256}",
        f"{evidence.variant}:board_all={evidence.board_all_positions_path}@{evidence.board_all_positions_sha256}",
        f"{evidence.variant}:board_all_command={evidence.board_all_command_path}@{evidence.board_all_command_sha256}",
        f"{evidence.variant}:board_fitted={evidence.board_fitted_positions_path}@{evidence.board_fitted_positions_sha256}",
        f"{evidence.variant}:board_fitted_command={evidence.board_fitted_command_path}@{evidence.board_fitted_command_sha256}",
    )


@dataclass(frozen=True, slots=True)
class PcbRequiredFittedReferenceCandidate(Candidate):
    """Finding retaining authored mismatch and its exact source inputs."""

    source_evidence: PcbRequiredFittedReferenceEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbRequiredFittedReferenceEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbRequiredFittedReferenceCandidate:
        projection = project_pcb_required_fitted_reference_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_required_fitted_reference_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Required fitted-reference rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Required fitted-reference evidence must match its projection")


@dataclass(frozen=True, slots=True)
class PcbBlockedRequiredFittedReferenceEvidence:
    """Blocked project requirement coverage with the enclosing inventory evidence."""

    report: PcbComponentInventoryCoverageReport

    def __post_init__(self) -> None:
        if self.report.required_fitted_reference_coverage.status != "BLOCKED":
            raise ValueError("Blocked fitted-reference evidence requires BLOCKED coverage")


def project_blocked_required_fitted_reference_evidence(
    source: PcbBlockedRequiredFittedReferenceEvidence,
) -> CandidateEvidenceProjection:
    """Project a blocked authored requirement check without implying a pass."""
    report = source.report
    coverage = report.required_fitted_reference_coverage
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "coverage_issue": (coverage.issue or "unavailable",),
            "requirement_map_sha256": (
                () if coverage.map_sha256 is None else (coverage.map_sha256,)
            ),
            "netlist_sha256": (() if report.netlist_sha256 is None else (report.netlist_sha256,)),
            "board_path": (() if report.board_path is None else (report.board_path,)),
            "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
            "snapshot_sha256": (
                () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbBlockedRequiredFittedReferenceCandidate(Candidate):
    """Blocked finding retaining the report that explains the coverage gap."""

    source_evidence: PcbBlockedRequiredFittedReferenceEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBlockedRequiredFittedReferenceEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbBlockedRequiredFittedReferenceCandidate:
        projection = project_blocked_required_fitted_reference_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_blocked_required_fitted_reference_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Blocked fitted-reference rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Blocked fitted-reference evidence must match its projection")
