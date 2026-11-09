"""Typed source projection for SWDIO/SWCLK same-net review candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .swd_endpoint_inventory import SwdEndpointInventory
from .swd_generic_connector_models import SwdDebugEndpoint

SWDIO_SWCLK_SAME_NET_RULE_ID: DesignLintRuleId = "bus.swdio_swclk_same_net"


@dataclass(frozen=True, slots=True)
class SwdIoClockSameNetEvidence:
    """One current native SWDIO/SWCLK endpoint pair assigned to one exact net."""

    observed: NetlistContract
    endpoint: SwdDebugEndpoint

    def __post_init__(self) -> None:
        current = SwdEndpointInventory.from_netlist(self.observed).endpoint_pairs(
            include_same_net=True
        )
        if self.endpoint not in current:
            raise ValueError("SWD same-net evidence must match a current native endpoint pair")
        if self.endpoint.swdio_net.casefold() != self.endpoint.swclk_net.casefold():
            raise ValueError("SWD same-net evidence requires one exact shared native net")


def project_swd_io_clock_same_net_evidence(
    source: SwdIoClockSameNetEvidence,
) -> CandidateEvidenceProjection:
    """Project native role, pin, and net observations into stable evidence fields."""
    endpoint = source.endpoint
    return CandidateEvidenceProjection(
        rule_id=SWDIO_SWCLK_SAME_NET_RULE_ID,
        evidence={
            "component": (endpoint.reference,),
            "SWDIO_pin": (endpoint.swdio_pin,),
            "SWDIO_function": (endpoint.swdio_function,),
            "SWDIO_electrical_type": (endpoint.swdio_electrical_type,),
            "SWCLK_pin": (endpoint.swclk_pin,),
            "SWCLK_function": (endpoint.swclk_function,),
            "SWCLK_electrical_type": (endpoint.swclk_electrical_type,),
            "shared_net": (endpoint.swdio_net,),
        },
    )


@dataclass(frozen=True, slots=True)
class SwdIoClockSameNetCandidate(Candidate):
    """Review prompt bound to the exact native SWD signal assignments."""

    source_evidence: SwdIoClockSameNetEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SwdIoClockSameNetEvidence,
        *,
        subject: str,
        message: str,
    ) -> SwdIoClockSameNetCandidate:
        projection = project_swd_io_clock_same_net_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_swd_io_clock_same_net_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("SWD same-net candidate must preserve its source projection")
