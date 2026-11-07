"""Review mapped pair routes that use different native copper-layer sequences."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_differential_pair_skew_models import (
    PcbDifferentialPairRouteSkewEntry,
    PcbDifferentialPairRouteSkewReport,
)

RULE_ID: DesignLintRuleId = "pcb.differential_pair_route_layer_mismatch"


def _layer_profile(layers: tuple[str, ...]) -> tuple[str, ...]:
    """Collapse adjacent same-layer tracks and normalize for comparison."""
    profile: list[str] = []
    for layer in layers:
        normalized = layer.casefold()
        if not profile or profile[-1] != normalized:
            profile.append(normalized)
    return tuple(profile)


def _display_profile(layers: tuple[str, ...]) -> str:
    profile: list[str] = []
    for layer in layers:
        if not profile or profile[-1].casefold() != layer.casefold():
            profile.append(layer)
    return " -> ".join(profile)


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairLayerTransitionFindingEvidence:
    """A fully resolved mapped bundle with different native layer profiles."""

    report: PcbDifferentialPairRouteSkewReport
    entry: PcbDifferentialPairRouteSkewEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Layer-transition evidence requires a usable route report")
        if self.entry not in self.report.entries:
            raise ValueError("Layer-transition entry must belong to its route report")
        if any(item.status != "RESOLVED" or not item.track_layers for item in self.entry.paths):
            raise ValueError("Layer-transition evidence requires every mapped route to resolve")
        if len({_layer_profile(item.track_layers) for item in self.entry.paths}) < 2:
            raise ValueError("Layer-transition evidence requires different route layer profiles")


def _project_layer_transition_evidence(
    source: PcbDifferentialPairLayerTransitionFindingEvidence,
) -> CandidateEvidenceProjection:
    entry = source.entry
    profiles = tuple(
        f"{path.path_id}: {path.net} {path.from_pad} to {path.to_pad}; "
        f"{_display_profile(path.track_layers)}"
        for path in sorted(entry.paths, key=lambda item: item.path_id.casefold())
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "bundle_id": (entry.bundle_id,),
            "basis": ("Project-authored exact pair endpoint map",),
            "route_layer_profiles": profiles,
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairLayerTransitionCandidate(Candidate):
    """Review cue for a mapped pair whose resolved copper-layer paths differ."""

    source_evidence: PcbDifferentialPairLayerTransitionFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDifferentialPairLayerTransitionFindingEvidence,
    ) -> PcbDifferentialPairLayerTransitionCandidate:
        projection = _project_layer_transition_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=f"{source_evidence.entry.bundle_id}: route layer transition comparison",
            message=(
                "The exact mapped pair routes use different copper-layer sequences. Review "
                "whether the transition difference is intentional; this is a geometry review "
                "cue and does not establish a signal-integrity defect or required layer profile."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_layer_transition_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Layer-transition rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Layer-transition finding must retain its exact route profiles")


def differential_pair_route_layer_candidates(
    report: PcbDifferentialPairRouteSkewReport,
) -> tuple[Candidate, ...]:
    """Compare exact resolved layer profiles for each authored pair bundle."""
    if report.status not in {"COMPLETE", "INCOMPLETE"}:
        return ()
    candidates: list[Candidate] = []
    for entry in sorted(report.entries, key=lambda item: item.bundle_id.casefold()):
        if any(path.status != "RESOLVED" or not path.track_layers for path in entry.paths):
            continue
        if len({_layer_profile(path.track_layers) for path in entry.paths}) < 2:
            continue
        candidates.append(
            PcbDifferentialPairLayerTransitionCandidate.from_source_evidence(
                PcbDifferentialPairLayerTransitionFindingEvidence(report=report, entry=entry)
            )
        )
    return tuple(candidates)
