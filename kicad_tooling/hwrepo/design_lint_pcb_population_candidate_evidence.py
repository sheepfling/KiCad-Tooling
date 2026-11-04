"""Typed source evidence and stable projection for PCB population findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_component_inventory_models import (
    PcbComponentInventorySourceReceipt,
    PcbPopulationMismatch,
    PcbVariantPopulationCoverage,
)


@dataclass(frozen=True, slots=True)
class PcbPopulationMismatchEvidence:
    """One DNP comparison with its native receipt and named-variant exports."""

    observation: PcbPopulationMismatch
    receipt: PcbComponentInventorySourceReceipt
    variant_population: PcbVariantPopulationCoverage


def project_pcb_population_evidence(
    source: PcbPopulationMismatchEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed DNP comparison and its source receipt to stable report fields."""
    observation = source.observation
    receipt = source.receipt
    evidence: dict[str, tuple[str, ...]] = {
        "reference": (observation.reference,),
        "schematic_dnp": (str(observation.schematic_dnp).lower(),),
        "board_dnp": (str(observation.board_dnp).lower(),),
        "netlist_sha256": (receipt.netlist_sha256 or "unavailable",),
        "board_path": (receipt.board_path or "unavailable",),
        "board_sha256": (receipt.board_sha256 or "unavailable",),
        "snapshot_sha256": (receipt.snapshot_sha256 or "unavailable",),
        "snapshot_schema": (receipt.snapshot_schema or "unavailable",),
        "kicad_version": (receipt.kicad_version or "unavailable",),
        "image": (receipt.image or "unavailable",),
        "probe_sha256": (receipt.probe_sha256 or "unavailable",),
    }
    evidence.update(
        project_named_variant_population_evidence(
            source.observation.variant,
            source.variant_population,
        )
    )
    return CandidateEvidenceProjection(
        rule_id="pcb.schematic_pcb_dnp_mismatch",
        evidence=evidence,
    )


def project_named_variant_population_evidence(
    variant: str | None,
    coverage: PcbVariantPopulationCoverage,
) -> dict[str, tuple[str, ...]]:
    """Project the exact paired export for a named variant, if one is available."""
    if variant is None:
        return {}
    exported = next((item for item in coverage.evidence if item.variant == variant), None)
    if exported is None:
        return {"variant": (variant,), "variant_evidence": ("unavailable",)}
    return {
        "variant": (variant,),
        "variant_project_path": (() if coverage.project_path is None else (coverage.project_path,)),
        "variant_project_sha256": (
            () if coverage.project_sha256 is None else (coverage.project_sha256,)
        ),
        "variant_schematic_path": (
            () if coverage.schematic_path is None else (coverage.schematic_path,)
        ),
        "variant_schematic_sha256": (
            () if coverage.schematic_sha256 is None else (coverage.schematic_sha256,)
        ),
        "variant_board_path": (() if coverage.board_path is None else (coverage.board_path,)),
        "variant_board_sha256": (() if coverage.board_sha256 is None else (coverage.board_sha256,)),
        "variant_board_probe_path": (
            ()
            if coverage.board_variant_probe_path is None
            else (coverage.board_variant_probe_path,)
        ),
        "variant_board_probe_sha256": (
            ()
            if coverage.board_variant_probe_sha256 is None
            else (coverage.board_variant_probe_sha256,)
        ),
        "variant_board_request_path": (
            ()
            if coverage.board_variant_request_path is None
            else (coverage.board_variant_request_path,)
        ),
        "variant_board_request_sha256": (
            ()
            if coverage.board_variant_request_sha256 is None
            else (coverage.board_variant_request_sha256,)
        ),
        "variant_board_probe_command_path": (
            ()
            if coverage.board_variant_command_path is None
            else (coverage.board_variant_command_path,)
        ),
        "variant_board_probe_command_sha256": (
            ()
            if coverage.board_variant_command_sha256 is None
            else (coverage.board_variant_command_sha256,)
        ),
        "variant_kicad_version": (
            () if coverage.kicad_version is None else (coverage.kicad_version,)
        ),
        "variant_image": (() if coverage.image is None else (coverage.image,)),
        "variant_netlist_path": (exported.netlist_path,),
        "variant_netlist_sha256": (exported.netlist_sha256,),
        "variant_netlist_command_path": (exported.netlist_command_path,),
        "variant_netlist_command_sha256": (exported.netlist_command_sha256,),
        "variant_board_all_positions_path": (exported.board_all_positions_path,),
        "variant_board_all_positions_sha256": (exported.board_all_positions_sha256,),
        "variant_board_all_command_path": (exported.board_all_command_path,),
        "variant_board_all_command_sha256": (exported.board_all_command_sha256,),
        "variant_board_fitted_positions_path": (exported.board_fitted_positions_path,),
        "variant_board_fitted_positions_sha256": (exported.board_fitted_positions_sha256,),
        "variant_board_fitted_command_path": (exported.board_fitted_command_path,),
        "variant_board_fitted_command_sha256": (exported.board_fitted_command_sha256,),
    }


@dataclass(frozen=True, slots=True)
class PcbPopulationCandidate(Candidate):
    """Per-reference population finding retaining its typed comparison."""

    source_evidence: PcbPopulationMismatchEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbPopulationMismatchEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbPopulationCandidate:
        projection = project_pcb_population_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_population_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("PCB population rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("PCB population evidence must match its typed source projection")


@dataclass(frozen=True, slots=True)
class PcbBlockedVariantPopulationEvidence:
    """Named-variant export evidence that is explicitly blocked."""

    coverage: PcbVariantPopulationCoverage

    def __post_init__(self) -> None:
        if self.coverage.status != "BLOCKED":
            raise ValueError("Blocked variant population evidence requires BLOCKED coverage")


def project_blocked_variant_population_evidence(
    source: PcbBlockedVariantPopulationEvidence,
) -> CandidateEvidenceProjection:
    """Project an unavailable named-variant comparison without implying coverage."""
    coverage = source.coverage
    return CandidateEvidenceProjection(
        rule_id="pcb.schematic_pcb_dnp_mismatch",
        evidence={
            "coverage_issue": (coverage.issue or "unavailable",),
            "project_path": () if coverage.project_path is None else (coverage.project_path,),
            "project_sha256": (
                () if coverage.project_sha256 is None else (coverage.project_sha256,)
            ),
            "schematic_path": (
                () if coverage.schematic_path is None else (coverage.schematic_path,)
            ),
            "schematic_sha256": (
                () if coverage.schematic_sha256 is None else (coverage.schematic_sha256,)
            ),
            "board_path": () if coverage.board_path is None else (coverage.board_path,),
            "board_sha256": () if coverage.board_sha256 is None else (coverage.board_sha256,),
            "kicad_version": (() if coverage.kicad_version is None else (coverage.kicad_version,)),
            "image": () if coverage.image is None else (coverage.image,),
            "board_variant_probe_sha256": (
                ()
                if coverage.board_variant_probe_sha256 is None
                else (coverage.board_variant_probe_sha256,)
            ),
            "board_variant_request_sha256": (
                ()
                if coverage.board_variant_request_sha256 is None
                else (coverage.board_variant_request_sha256,)
            ),
            "board_variant_command_sha256": (
                ()
                if coverage.board_variant_command_sha256 is None
                else (coverage.board_variant_command_sha256,)
            ),
            "partial_variant_exports": tuple(
                f"{item.variant}:{item.netlist_sha256}:"
                f"{item.board_all_positions_sha256}:{item.board_fitted_positions_sha256}"
                for item in coverage.evidence
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbBlockedVariantPopulationCandidate(Candidate):
    """Coverage finding retaining its explicit blocked named-variant source."""

    source_evidence: PcbBlockedVariantPopulationEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBlockedVariantPopulationEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbBlockedVariantPopulationCandidate:
        projection = project_blocked_variant_population_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_blocked_variant_population_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("PCB population rule must match its blocked variant evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Blocked variant evidence must match its typed source projection")
