"""Typed source evidence and projection for PCB reference-plane findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_reference_plane_models import (
    PcbReferencePlaneCoverageEntry,
    PcbReferencePlaneCoverageReport,
)

RULE_ID: DesignLintRuleId = "pcb.reference_plane_coverage"


def reference_plane_below_threshold_track_uuids(
    entry: PcbReferencePlaneCoverageEntry,
) -> tuple[str, ...]:
    """Return tracks below threshold on every measured reference layer."""
    by_track: dict[str, list[bool]] = {}
    for item in entry.tracks:
        by_track.setdefault(item.track_uuid, []).append(item.below_minimum)
    return tuple(
        sorted(
            (track_uuid for track_uuid, layers in by_track.items() if all(layers)),
            key=str.casefold,
        )
    )


@dataclass(frozen=True, slots=True)
class PcbReferencePlaneFindingEvidence:
    """A mapped plane comparison and its complete source-bound coverage report."""

    report: PcbReferencePlaneCoverageReport
    entry: PcbReferencePlaneCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Reference-plane finding evidence requires scanned coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Reference-plane finding must belong to the source report")
        if self.entry.status == "COMPLETE" and not self.below_threshold_track_uuids:
            raise ValueError("Reference-plane control coverage emits no finding")

    @property
    def below_threshold_track_uuids(self) -> tuple[str, ...]:
        """Return tracks below threshold on every measured reference layer."""
        return reference_plane_below_threshold_track_uuids(self.entry)

    @property
    def endpoint_via_hole_candidates(self) -> tuple[str, ...]:
        """Return below-threshold endpoint vias whose centers lie in reference holes."""
        return tuple(
            sorted(
                {
                    via_id
                    for item in self.entry.tracks
                    if item.track_uuid in self.below_threshold_track_uuids
                    for via_id in item.endpoint_via_ids_with_center_in_reference_holes
                },
                key=str.casefold,
            )
        )


def project_pcb_reference_plane_evidence(
    source: PcbReferencePlaneFindingEvidence,
) -> CandidateEvidenceProjection:
    """Preserve per-track centerline coverage and endpoint-via context."""
    entry = source.entry
    measurements = tuple(
        f"{item.track_uuid}: {item.signal_layer} over {item.reference_layer}; "
        f"covered {item.covered_fraction_numerator}/"
        f"{item.covered_fraction_denominator}; "
        f"minimum {entry.minimum_referenced_fraction}; "
        f"zones {', '.join(item.reference_zone_uuids) or 'none'}; "
        f"endpoint vias {', '.join(item.endpoint_via_ids) or 'none'}; "
        "endpoint via centers in reference holes "
        f"{', '.join(item.endpoint_via_ids_with_center_in_reference_holes) or 'none'}"
        for item in entry.tracks
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "signal_net": (entry.signal_net,),
            "signal_layers": entry.signal_layers,
            "reference_net": (entry.reference_net,),
            "minimum_track_length_um": (str(entry.minimum_track_length_um),),
            "minimum_referenced_fraction": (str(entry.minimum_referenced_fraction),),
            "review_excluded_short_tracks": (str(entry.review_excluded_short_tracks).lower(),),
            "measured_tracks": measurements,
            "below_threshold_track_uuids": source.below_threshold_track_uuids,
            "endpoint_via_hole_candidates": source.endpoint_via_hole_candidates,
            "excluded_short_track_uuids": entry.excluded_short_track_uuids,
            "coverage_status": (entry.status,),
            "basis": (entry.basis,),
            "issues": entry.issues,
            "metric": (
                "Exact rational share of each native straight-track centerline "
                + "inside the union of filled same-net zones on each immediately "
                + "adjacent copper layer, measured independently per layer",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbReferencePlaneCandidate(Candidate):
    """Reference-plane finding retaining its exact track evidence and source report."""

    source_evidence: PcbReferencePlaneFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbReferencePlaneFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbReferencePlaneCandidate:
        projection = project_pcb_reference_plane_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_reference_plane_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Reference-plane evidence must match its source projection")
