"""Typed source projection for I2S clock/frame same-net review candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i2s_endpoint_inventory import I2sClockFrameEndpoint, I2sEndpointInventory
from .netlist_contract_models import NetlistContract

I2S_CLOCK_FRAME_SAME_NET_RULE_ID: DesignLintRuleId = "bus.i2s_clock_frame_same_net"


@dataclass(frozen=True, slots=True)
class I2sClockFrameSameNetEvidence:
    """One current native I2S clock/frame pair assigned to a shared net."""

    observed: NetlistContract
    endpoint: I2sClockFrameEndpoint

    def __post_init__(self) -> None:
        current = I2sEndpointInventory.from_netlist(self.observed).clock_frame_endpoints()
        if self.endpoint not in current:
            raise ValueError("I2S same-net evidence must match a current native endpoint pair")
        if self.endpoint.bit_clock_net.casefold() != self.endpoint.word_select_net.casefold():
            raise ValueError("I2S same-net evidence requires one exact shared native net")


def project_i2s_clock_frame_same_net_evidence(
    source: I2sClockFrameSameNetEvidence,
) -> CandidateEvidenceProjection:
    """Project role pins, metadata, and the shared net into stable evidence."""
    endpoint = source.endpoint
    return CandidateEvidenceProjection(
        rule_id=I2S_CLOCK_FRAME_SAME_NET_RULE_ID,
        evidence={
            "component": (endpoint.reference,),
            "bit_clock_pin": (endpoint.bit_clock_pin,),
            "bit_clock_function": (endpoint.bit_clock_function,),
            "bit_clock_electrical_type": (endpoint.bit_clock_electrical_type,),
            "word_select_pin": (endpoint.word_select_pin,),
            "word_select_function": (endpoint.word_select_function,),
            "word_select_electrical_type": (endpoint.word_select_electrical_type,),
            "shared_net": (endpoint.bit_clock_net,),
        },
    )


@dataclass(frozen=True, slots=True)
class I2sClockFrameSameNetCandidate(Candidate):
    """Review candidate bound to the source pins and assignment that triggered it."""

    source_evidence: I2sClockFrameSameNetEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: I2sClockFrameSameNetEvidence,
        *,
        subject: str,
        message: str,
    ) -> I2sClockFrameSameNetCandidate:
        projection = project_i2s_clock_frame_same_net_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_i2s_clock_frame_same_net_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("I2S candidate must preserve its native source projection")
