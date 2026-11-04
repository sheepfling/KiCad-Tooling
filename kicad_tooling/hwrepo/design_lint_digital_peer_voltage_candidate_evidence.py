"""Typed evidence projection for shared SPI and serial peer-voltage findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .digital_peer_voltage_scan import format_nominal_voltage
from .digital_peer_voltage_types import (
    DigitalPeerVoltageLintContext,
    DigitalPeerVoltageReview,
)

_SPI_PEER_VOLTAGE: DesignLintRuleId = "bus.spi_peer_voltage_review"
_SERIAL_PEER_VOLTAGE: DesignLintRuleId = "bus.serial_peer_voltage_review"


@dataclass(frozen=True, slots=True)
class DigitalPeerVoltageFindingEvidence:
    """One grouped native peer review and the authored-map scope used to assess it."""

    peer: DigitalPeerVoltageReview
    scope: DigitalPeerVoltageLintContext


def project_digital_peer_voltage_evidence(
    source: DigitalPeerVoltageFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project one protocol-specific peer review into stable report fields."""
    peer = source.peer
    assignment_key = (
        "shared_SPI_pin_assignments" if peer.interface == "SPI" else "shared_serial_pin_assignments"
    )
    rule_id = _SPI_PEER_VOLTAGE if peer.interface == "SPI" else _SERIAL_PEER_VOLTAGE
    evidence = {
        "output_component": (peer.output_reference,),
        "input_component": (peer.input_reference,),
        "output_supply_net": (peer.output_rail.net,),
        "output_supply_label_value": (format_nominal_voltage(peer.output_rail.voltage_v),),
        "input_supply_net": (peer.input_rail.net,),
        "input_supply_label_value": (format_nominal_voltage(peer.input_rail.voltage_v),),
        assignment_key: tuple(
            f"{link.net}: {link.output_pin} ({link.output_function}, {link.output_type}) -> "
            f"{link.input_pin} ({link.input_function}, {link.input_type})"
            for link in peer.links
        ),
        "authored_voltage_map_state": (source.scope.state,),
    }
    if source.scope.source_path is not None:
        evidence["electrical_contract_path"] = (source.scope.source_path,)
    if source.scope.source_sha256 is not None:
        evidence["electrical_contract_sha256"] = (source.scope.source_sha256,)
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class DigitalPeerVoltageCandidate(Candidate):
    """Peer-voltage candidate retaining its typed native and authored sources."""

    source_evidence: DigitalPeerVoltageFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: DigitalPeerVoltageFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> DigitalPeerVoltageCandidate:
        projection = project_digital_peer_voltage_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_digital_peer_voltage_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Digital peer-voltage fields must match their typed source projection")
