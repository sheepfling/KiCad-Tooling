"""Translate pair reference-via evidence into stable PCB review candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_differential_pair_reference_via_models import (
    PcbDifferentialPairReferenceViaEntry,
    PcbDifferentialPairReferenceViaReport,
)

RULE_ID: DesignLintRuleId = "pcb.differential_pair_reference_via_stitching"


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairReferenceViaFindingEvidence:
    """One source-bound pair whose transition evidence needs electrical review."""

    report: PcbDifferentialPairReferenceViaReport
    entry: PcbDifferentialPairReferenceViaEntry | None = None

    def __post_init__(self) -> None:
        if self.report.status == "BLOCKED":
            if self.entry is not None:
                raise ValueError("Blocked reference-via coverage has no measured pair entry")
            return
        if (
            self.report.status != "INCOMPLETE"
            or self.entry is None
            or self.entry not in self.report.entries
        ):
            raise ValueError(
                "Reference-via finding must belong to incomplete source-bound evidence"
            )
        if self.entry.status == "WITHIN_LIMIT":
            raise ValueError("A within-limit pair cannot produce a reference-via finding")


def _project_reference_via_evidence(
    source: PcbDifferentialPairReferenceViaFindingEvidence,
) -> CandidateEvidenceProjection:
    entry = source.entry
    if entry is None:
        return CandidateEvidenceProjection(
            rule_id=RULE_ID,
            evidence={
                "bundle_id": source.report.configured_bundle_ids,
                "reference_net": (),
                "maximum_distance_nm": (),
                "transitions": (),
                "issues": () if source.report.issue is None else (source.report.issue,),
            },
        )
    transitions = tuple(
        f"{item.path_id}: {item.from_layer or 'unknown'} -> {item.to_layer or 'unknown'}; "
        f"signal via {item.signal_via_id or 'unavailable'}; nearest compatible reference via "
        f"{item.nearest_reference_via_id or 'none'} at "
        f"{item.nearest_distance_nm if item.nearest_distance_nm is not None else 'unavailable'} nm; "
        f"distance^2 {item.nearest_distance_squared_nm2 if item.nearest_distance_squared_nm2 is not None else 'unavailable'} nm^2; "
        f"{item.status}" + (f"; {item.issue}" if item.issue is not None else "")
        for item in entry.transitions
    )
    issues = () if entry.issue is None else (entry.issue,)
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "bundle_id": (entry.bundle_id,),
            "reference_net": (entry.reference_net,),
            "maximum_distance_nm": (str(entry.max_distance_nm),),
            "transitions": transitions,
            "issues": issues,
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairReferenceViaCandidate(Candidate):
    """Review cue for a pair transition without a nearby authored reference via."""

    source_evidence: PcbDifferentialPairReferenceViaFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDifferentialPairReferenceViaFindingEvidence,
    ) -> PcbDifferentialPairReferenceViaCandidate:
        projection = _project_reference_via_evidence(source_evidence)
        entry = source_evidence.entry
        if entry is None:
            bundle_ids = ", ".join(source_evidence.report.configured_bundle_ids)
            return cls(
                rule_id=projection.rule_id,
                subject=f"{bundle_ids}: pair reference-via coverage unavailable",
                message=(
                    "The configured pair reference-via check could not run against current "
                    "source-bound native PCB evidence. Resolve the coverage issue before treating "
                    "the reference-via heuristic as clean."
                ),
                evidence=projection.evidence,
                source_evidence=source_evidence,
            )
        return cls(
            rule_id=projection.rule_id,
            subject=f"{entry.bundle_id}: differential-pair reference-via review",
            message=(
                "At least one mapped pair transition has no source-observed via on the "
                f"project-authored {entry.reference_net!r} reference net within "
                f"{entry.max_distance_nm} nm, or its native evidence is incomplete. Review the "
                "return-current path and plane continuity. This proximity heuristic does not "
                "prove reference-plane connection, signal integrity, or electrical intent."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_reference_via_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Reference-via finding must retain its exact source evidence")


def differential_pair_reference_via_candidates(
    report: PcbDifferentialPairReferenceViaReport,
) -> tuple[Candidate, ...]:
    """Return one review candidate per configured pair with missing or incomplete transitions."""
    if report.status == "BLOCKED":
        return (
            PcbDifferentialPairReferenceViaCandidate.from_source_evidence(
                PcbDifferentialPairReferenceViaFindingEvidence(report=report)
            ),
        )
    if report.status != "INCOMPLETE":
        return ()
    return tuple(
        PcbDifferentialPairReferenceViaCandidate.from_source_evidence(
            PcbDifferentialPairReferenceViaFindingEvidence(report=report, entry=entry)
        )
        for entry in sorted(report.entries, key=lambda item: item.bundle_id.casefold())
        if entry.status != "WITHIN_LIMIT"
    )
