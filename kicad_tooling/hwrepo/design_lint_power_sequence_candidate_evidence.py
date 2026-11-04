"""Typed source evidence and projection for mapped power-sequence findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .model_primitives import Digest
from .power_sequence_models import PowerSequenceMap, power_sequence_map_sha256
from .power_sequences import (
    PowerSequenceMismatch,
    PowerSequenceObservedCycle,
    power_sequence_graph_has_cycle,
)

RULE_ID: DesignLintRuleId = "power.mapped_sequence_dependency_mismatch"


@dataclass(frozen=True, slots=True)
class PowerSequenceMismatchFindingEvidence:
    """One native stage mismatch and the authored map that defines its endpoints."""

    sequence_map: PowerSequenceMap
    mismatch: PowerSequenceMismatch

    def __post_init__(self) -> None:
        stage = next(
            (
                item
                for item in self.sequence_map.stages
                if item.id.casefold() == self.mismatch.stage_id.casefold()
            ),
            None,
        )
        if stage is None:
            raise ValueError("Power-sequence mismatch must name a stage in the source map")
        expected_endpoints = tuple(
            f"{role}: {endpoint.pin} on {endpoint.net}"
            for role, endpoint in (
                ("output", stage.output),
                ("power_good", stage.power_good),
                ("enable", stage.enable),
            )
            if endpoint is not None
        )
        if (
            self.mismatch.stage_basis != stage.basis
            or self.mismatch.enable_control != stage.enable_control
            or self.mismatch.expected_endpoints != expected_endpoints
            or self.mismatch.output_pin != stage.output.pin
            or self.mismatch.output_net != stage.output.net
            or not self.mismatch.issues
        ):
            raise ValueError("Power-sequence mismatch must match its authored stage")

    @property
    def map_sha256(self) -> Digest:
        """Return the source-map digest used by the report projection."""
        return power_sequence_map_sha256(self.sequence_map)


@dataclass(frozen=True, slots=True)
class PowerSequenceCycleFindingEvidence:
    """A declared or native output-to-enable cycle bound to its source map."""

    sequence_map: PowerSequenceMap
    declared_dependency_cycle: bool
    observed_cycles: tuple[PowerSequenceObservedCycle, ...] = ()

    def __post_init__(self) -> None:
        if self.declared_dependency_cycle != power_sequence_graph_has_cycle(self.sequence_map):
            raise ValueError("Declared cycle state must match the source dependency graph")
        known_stages = {stage.id.casefold() for stage in self.sequence_map.stages}
        if any(
            not {stage.casefold() for stage in cycle.stage_ids} <= known_stages
            for cycle in self.observed_cycles
        ):
            raise ValueError("Observed power-sequence cycles must name mapped stages")
        if not self.declared_dependency_cycle and not self.observed_cycles:
            raise ValueError("Power-sequence cycle evidence requires an observed cycle")

    @property
    def map_sha256(self) -> Digest:
        """Return the source-map digest used by the report projection."""
        return power_sequence_map_sha256(self.sequence_map)

    @property
    def issues(self) -> tuple[str, ...]:
        """Describe the exact authored and native cycle conditions."""
        return (
            *(
                ("The project-authored dependency graph is cyclic",)
                if self.declared_dependency_cycle
                else ()
            ),
            *(
                "The mapped native output-to-enable topology is cyclic across stages "
                + ", ".join(cycle.stage_ids)
                for cycle in self.observed_cycles
            ),
        )


PowerSequenceFindingEvidence: TypeAlias = (
    PowerSequenceMismatchFindingEvidence | PowerSequenceCycleFindingEvidence
)


def project_power_sequence_evidence(
    source: PowerSequenceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project one exact mismatch or cycle source to the existing report fields."""
    if isinstance(source, PowerSequenceMismatchFindingEvidence):
        mismatch = source.mismatch
        neighboring_stages = {mismatch.stage_id.casefold()}
        return CandidateEvidenceProjection(
            rule_id=RULE_ID,
            evidence={
                "sequence_map_basis": (source.sequence_map.basis,),
                "stage": (mismatch.stage_id,),
                "stage_basis": (mismatch.stage_basis,),
                "enable_control": (mismatch.enable_control,),
                "expected_endpoints": mismatch.expected_endpoints,
                "dependencies": tuple(
                    f"{item.id}: {item.predecessor_stage} → "
                    f"{item.successor_stage} on {item.signal_net}"
                    for item in source.sequence_map.dependencies
                    if neighboring_stages
                    & {item.predecessor_stage.casefold(), item.successor_stage.casefold()}
                ),
                "output_endpoint": (f"{mismatch.output_pin} on {mismatch.output_net}",),
                "map_sha256": (source.map_sha256,),
                "issues": mismatch.issues,
            },
        )

    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "sequence_map_basis": (source.sequence_map.basis,),
            "dependencies": tuple(
                f"{item.predecessor_stage} → {item.successor_stage} on {item.signal_net}"
                for item in source.sequence_map.dependencies
            ),
            "declared_dependency_cycle": (str(source.declared_dependency_cycle).lower(),),
            "observed_output_to_enable_cycle_stages": tuple(
                ", ".join(cycle.stage_ids) for cycle in source.observed_cycles
            ),
            "observed_output_to_enable_cycle_edges": tuple(
                edge for cycle in source.observed_cycles for edge in cycle.edges
            ),
            "map_sha256": (source.map_sha256,),
            "issues": source.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class PowerSequenceCandidate(Candidate):
    """Power-sequence finding retaining the exact mismatch or cycle source."""

    source_evidence: PowerSequenceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PowerSequenceFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PowerSequenceCandidate:
        projection = project_power_sequence_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_power_sequence_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Power-sequence evidence must match its source projection")
