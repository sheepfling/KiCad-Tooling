"""Typed control-input sources and their stable finding projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .control_input_inventory import (
    ControlInputBiasGap,
    UnconnectedControlInput,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .open_drain_heuristics import OpenOutputBiasGap

ControlCandidateEvidence: TypeAlias = (
    UnconnectedControlInput | ControlInputBiasGap | OpenOutputBiasGap
)


def open_output_expected_bias_description(source: OpenOutputBiasGap) -> str:
    """Describe the rail direction the existing open-output rule reports."""
    return (
        "pull-up to a recognized positive rail"
        if source.bias == "pull_up"
        else "pull-down to a recognized return"
    )


def project_control_candidate_evidence(
    source: ControlCandidateEvidence,
) -> CandidateEvidenceProjection:
    """Project one typed scan record to the established report fields."""
    if isinstance(source, UnconnectedControlInput):
        return CandidateEvidenceProjection(
            rule_id="control.unconnected_control_input",
            evidence={
                source.pin: (),
                "function": (source.function,),
                "family": (source.family,),
                "electrical_type": (source.electrical_type,),
            },
        )
    if isinstance(source, ControlInputBiasGap):
        controls = tuple(
            f"{control.pin}: {control.function} ({control.family}, {control.electrical_type})"
            for control in source.controls
        )
        return CandidateEvidenceProjection(
            rule_id="control.connected_control_input_without_visible_bias",
            evidence={
                "net": (source.net,),
                "control_inputs": controls,
                "output_capable_peers": source.output_capable_peers,
            },
        )

    return CandidateEvidenceProjection(
        rule_id=(
            "signal.open_collector_input_without_visible_bias"
            if source.bias == "pull_up"
            else "signal.open_emitter_input_without_visible_bias"
        ),
        evidence={
            "net": (source.net,),
            "expected_bias": (open_output_expected_bias_description(source),),
            "open_output_pins": source.output_pins,
            "input_pins": source.input_pins,
            "visible_resistors_on_signal_net": source.visible_resistors,
        },
    )


@dataclass(frozen=True, slots=True)
class ControlCandidate(Candidate):
    """Internal control finding retaining its typed scan source."""

    source_evidence: ControlCandidateEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ControlCandidateEvidence,
        *,
        subject: str,
        message: str,
    ) -> ControlCandidate:
        projection = project_control_candidate_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_control_candidate_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Control candidate rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Control finding evidence must match its typed source projection")
