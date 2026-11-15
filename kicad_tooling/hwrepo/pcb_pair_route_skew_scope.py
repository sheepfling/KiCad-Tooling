"""Review authored differential-pair skew bounds without route-bundle scope."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_models import PcbDifferentialPairRuleMap, PcbDifferentialPairRuleRequirement
from .pcb_signal_path_rule_models import PcbSignalPathRuleMap

RULE_ID: DesignLintRuleId = "pcb.differential_pair_route_skew_scope_missing"


def _map_digest(model: PcbDifferentialPairRuleMap | PcbSignalPathRuleMap | None) -> str:
    if model is None:
        return "absent"
    return sha256(model.model_dump_json().encode("utf-8")).hexdigest()


def _pair_path_ids(
    requirement: PcbDifferentialPairRuleRequirement,
    signal_path_map: PcbSignalPathRuleMap | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if signal_path_map is None:
        return (), ()
    positive = tuple(
        sorted(
            (
                path.id
                for path in signal_path_map.paths
                if path.net.casefold() == requirement.positive_net.casefold()
            ),
            key=lambda item: (item.casefold(), item),
        )
    )
    negative = tuple(
        sorted(
            (
                path.id
                for path in signal_path_map.paths
                if path.net.casefold() == requirement.negative_net.casefold()
            ),
            key=lambda item: (item.casefold(), item),
        )
    )
    return positive, negative


def _covering_skew_bundles(
    requirement: PcbDifferentialPairRuleRequirement,
    signal_path_map: PcbSignalPathRuleMap | None,
) -> tuple[str, ...]:
    if signal_path_map is None:
        return ()
    path_nets = {path.id.casefold(): path.net.casefold() for path in signal_path_map.paths}
    target_nets = {requirement.positive_net.casefold(), requirement.negative_net.casefold()}
    return tuple(
        sorted(
            (
                bundle.id
                for bundle in signal_path_map.bundles
                if bundle.max_skew is not None
                and target_nets.issubset(
                    {path_nets[path_id.casefold()] for path_id in bundle.path_ids}
                )
            ),
            key=lambda item: (item.casefold(), item),
        )
    )


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairRouteSkewScopeEvidence:
    """Authored pair and route maps showing absent skew-bundle coverage."""

    pair_map: PcbDifferentialPairRuleMap
    signal_path_map: PcbSignalPathRuleMap | None
    requirement: PcbDifferentialPairRuleRequirement

    def __post_init__(self) -> None:
        if self.requirement not in self.pair_map.requirements:
            raise ValueError("Route-skew scope evidence requirement must belong to its pair map")
        if self.requirement.skew is None:
            raise ValueError("Route-skew scope evidence requires an authored pair skew bound")
        if _covering_skew_bundles(self.requirement, self.signal_path_map):
            raise ValueError("Route-skew scope evidence must lack a covering skew bundle")

    @property
    def member_path_ids(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return _pair_path_ids(self.requirement, self.signal_path_map)


def project_pcb_differential_pair_route_skew_scope(
    source: PcbDifferentialPairRouteSkewScopeEvidence,
) -> CandidateEvidenceProjection:
    """Project both map identities and exact pair-path coverage to stable evidence."""
    requirement = source.requirement
    skew = requirement.skew
    if skew is None:
        raise ValueError("Route-skew scope evidence requires an authored pair skew bound")
    positive_paths, negative_paths = source.member_path_ids
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "pair_requirement_id": (requirement.id,),
            "positive_net": (requirement.positive_net,),
            "negative_net": (requirement.negative_net,),
            "declared_max_skew_nm": (str(skew.max_nm),),
            "positive_signal_path_ids": positive_paths,
            "negative_signal_path_ids": negative_paths,
            "pair_map_sha256": (_map_digest(source.pair_map),),
            "signal_path_map_sha256": (_map_digest(source.signal_path_map),),
            "basis": (requirement.basis,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairRouteSkewScopeCandidate(Candidate):
    """Review finding retaining its typed, independently authored map sources."""

    source_evidence: PcbDifferentialPairRouteSkewScopeEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDifferentialPairRouteSkewScopeEvidence,
    ) -> PcbDifferentialPairRouteSkewScopeCandidate:
        requirement = source_evidence.requirement
        projection = project_pcb_differential_pair_route_skew_scope(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=f"{requirement.id}: {requirement.positive_net} / {requirement.negative_net}",
            message=(
                "Review whether this pair's authored DRC skew bound also needs a "
                "project-mapped signal-path skew bundle. Local route-skew measurement "
                "requires a bundle containing paths on both exact pair nets; no such "
                "bundle is present. This prompt does not infer path endpoints or limits."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_differential_pair_route_skew_scope(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Route-skew scope evidence must match its source projection")


def pcb_differential_pair_route_skew_scope_candidates(
    pair_map: PcbDifferentialPairRuleMap | None,
    signal_path_map: PcbSignalPathRuleMap | None,
    *,
    is_pcb_project: bool,
) -> tuple[Candidate, ...]:
    """Review skew-bounded pairs without one complete mapped route-skew bundle."""
    if not is_pcb_project or pair_map is None:
        return ()
    found = (
        PcbDifferentialPairRouteSkewScopeCandidate.from_source_evidence(
            PcbDifferentialPairRouteSkewScopeEvidence(
                pair_map=pair_map,
                signal_path_map=signal_path_map,
                requirement=requirement,
            )
        )
        for requirement in pair_map.requirements
        if requirement.skew is not None and not _covering_skew_bundles(requirement, signal_path_map)
    )
    return tuple(
        sorted(
            found,
            key=lambda item: (item.subject.casefold(), item.subject),
        )
    )
