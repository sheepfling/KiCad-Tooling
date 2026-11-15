"""Review differential-pair maps that omit reference-plane scope."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_models import PcbDifferentialPairRuleMap, PcbDifferentialPairRuleRequirement
from .pcb_reference_plane_models import PcbReferencePlaneMap

RULE_ID: DesignLintRuleId = "pcb.differential_pair_reference_plane_scope_missing"


def _model_digest(model: PcbDifferentialPairRuleMap | PcbReferencePlaneMap | None) -> str:
    if model is None:
        return "absent"
    return sha256(model.model_dump_json().encode("utf-8")).hexdigest()


def _missing_plane_nets(
    requirement: PcbDifferentialPairRuleRequirement,
    reference_plane_map: PcbReferencePlaneMap | None,
) -> tuple[str, ...]:
    covered: set[str] = set()
    if reference_plane_map is not None:
        covered = {item.signal_net.casefold() for item in reference_plane_map.requirements}
    return tuple(
        net
        for net in (requirement.positive_net, requirement.negative_net)
        if net.casefold() not in covered
    )


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairPlaneScopeEvidence:
    """Authored pair and plane maps showing which pair nets lack plane scope."""

    pair_map: PcbDifferentialPairRuleMap
    reference_plane_map: PcbReferencePlaneMap | None
    requirement: PcbDifferentialPairRuleRequirement

    def __post_init__(self) -> None:
        if self.requirement not in self.pair_map.requirements:
            raise ValueError("Pair-plane evidence requirement must belong to its pair map")
        if not _missing_plane_nets(self.requirement, self.reference_plane_map):
            raise ValueError("Pair-plane evidence must identify an unmapped pair net")

    @property
    def missing_nets(self) -> tuple[str, ...]:
        return _missing_plane_nets(self.requirement, self.reference_plane_map)


def project_pcb_differential_pair_plane_scope(
    source: PcbDifferentialPairPlaneScopeEvidence,
) -> CandidateEvidenceProjection:
    """Project map identity and exact omitted pair nets to stable lint evidence."""
    requirement = source.requirement
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "pair_requirement_id": (requirement.id,),
            "positive_net": (requirement.positive_net,),
            "negative_net": (requirement.negative_net,),
            "pair_selector": (requirement.pair_selector,),
            "declared_pair_constraints": tuple(
                name
                for name in (
                    "track_width",
                    "diff_pair_gap",
                    "skew",
                    "uncoupled_length",
                    "edge_clearance",
                )
                if getattr(requirement, name) is not None
            ),
            "missing_reference_plane_nets": source.missing_nets,
            "pair_map_sha256": (_model_digest(source.pair_map),),
            "reference_plane_map_sha256": (_model_digest(source.reference_plane_map),),
            "basis": (requirement.basis,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairPlaneScopeCandidate(Candidate):
    """Review finding retaining its typed, independently authored map sources."""

    source_evidence: PcbDifferentialPairPlaneScopeEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDifferentialPairPlaneScopeEvidence,
    ) -> PcbDifferentialPairPlaneScopeCandidate:
        requirement = source_evidence.requirement
        projection = project_pcb_differential_pair_plane_scope(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(f"{requirement.id}: {requirement.positive_net} / {requirement.negative_net}"),
            message=(
                "Review whether this explicitly mapped differential pair needs an independent "
                "PCB reference-plane coverage requirement. The plane map omits "
                f"{', '.join(source_evidence.missing_nets)}. This is a coverage prompt only; "
                "it does not require a reference net, common ground, layer, or threshold."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_differential_pair_plane_scope(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Pair-plane evidence must match its source projection")


def pcb_differential_pair_reference_plane_scope_candidates(
    pair_map: PcbDifferentialPairRuleMap | None,
    reference_plane_map: PcbReferencePlaneMap | None,
    *,
    is_pcb_project: bool,
) -> tuple[Candidate, ...]:
    """Review mapped differential pairs with one or more absent plane-map scopes."""
    if not is_pcb_project or pair_map is None:
        return ()
    found = (
        PcbDifferentialPairPlaneScopeCandidate.from_source_evidence(
            PcbDifferentialPairPlaneScopeEvidence(
                pair_map=pair_map,
                reference_plane_map=reference_plane_map,
                requirement=requirement,
            )
        )
        for requirement in pair_map.requirements
        if _missing_plane_nets(requirement, reference_plane_map)
    )
    return tuple(
        sorted(
            found,
            key=lambda item: (item.subject.casefold(), item.subject),
        )
    )
