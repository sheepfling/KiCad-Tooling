"""Typed source projections for serial-peer coverage and reference findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .serial_participants import SerialPeerRosterContext, UnmappedSerialPeer
from .serial_peer_reference_types import (
    SerialPeerReferenceReview,
    SerialPeerReferenceScan,
)


@dataclass(frozen=True, slots=True)
class UnmappedSerialPeerFindingEvidence:
    """One discovered endpoint and its authored peer-map scope."""

    peer: UnmappedSerialPeer
    scope: SerialPeerRosterContext


@dataclass(frozen=True, slots=True)
class SerialPeerReferenceFindingEvidence:
    """One review group bound to its full scan and authored peer-map scope."""

    scan: SerialPeerReferenceScan
    review: SerialPeerReferenceReview
    scope: SerialPeerRosterContext

    def __post_init__(self) -> None:
        if not any(candidate is self.review for candidate in self.scan.reviews):
            raise ValueError("Serial reference review must belong to its source scan")


SerialPeerFindingSource: TypeAlias = (
    UnmappedSerialPeerFindingEvidence | SerialPeerReferenceFindingEvidence
)

_UNMAPPED_SERIAL_PEER: DesignLintRuleId = "bus.serial_unmapped_peer"
_SERIAL_PEER_REFERENCE: DesignLintRuleId = "bus.serial_peer_reference_review"


def _project_unmapped_peer(
    source: UnmappedSerialPeerFindingEvidence,
) -> CandidateEvidenceProjection:
    peer = source.peer
    evidence = {
        "interface_channel": (peer.channel,),
        "TX_pins": peer.tx_pins,
        "RX_pins": peer.rx_pins,
        "assigned_signal_pins": peer.signal_assignments,
        "discovery_basis": (peer.discovery_basis,),
        "serial_peer_map_state": (source.scope.state,),
    }
    if source.scope.source_path is not None:
        evidence["electrical_contract_path"] = (source.scope.source_path,)
    if source.scope.source_sha256 is not None:
        evidence["electrical_contract_sha256"] = (source.scope.source_sha256,)
    return CandidateEvidenceProjection(rule_id=_UNMAPPED_SERIAL_PEER, evidence=evidence)


def _project_reference_review(
    source: SerialPeerReferenceFindingEvidence,
) -> CandidateEvidenceProjection:
    peer = source.review
    shared_links = tuple(
        f"{link.net}: {link.output_pin} ({link.output_function}, {link.output_type}) -> "
        f"{link.input_pin} ({link.input_function}, {link.input_type})"
        for link in peer.links
    )
    evidence = {
        "first_component": (peer.first_reference,),
        "second_component": (peer.second_reference,),
        "first_reference_net": (peer.first_reference_domain.net,),
        "first_reference_pin_assignments": tuple(
            f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
            for item in peer.first_reference_domain.pins
        ),
        "second_reference_net": (peer.second_reference_domain.net,),
        "second_reference_pin_assignments": tuple(
            f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
            for item in peer.second_reference_domain.pins
        ),
        "serial_peer_map_state": (source.scope.state,),
    }
    if peer.links:
        evidence["shared_serial_pin_assignments"] = shared_links
    if peer.label_links:
        evidence["serial_label_link_assignments"] = tuple(
            f"{link.channel}: TX {link.tx_net} ({link.first_tx_pin}, {link.second_tx_pin}); "
            f"RX {link.rx_net} ({link.first_rx_pin}, {link.second_rx_pin})"
            for link in peer.label_links
        )
        evidence["discovery_basis"] = (
            ("native_pin_function", "net_label") if peer.links else ("net_label",)
        )
    if source.scope.source_path is not None:
        evidence["electrical_contract_path"] = (source.scope.source_path,)
    if source.scope.source_sha256 is not None:
        evidence["electrical_contract_sha256"] = (source.scope.source_sha256,)
    return CandidateEvidenceProjection(rule_id=_SERIAL_PEER_REFERENCE, evidence=evidence)


def project_serial_peer_evidence(
    source: SerialPeerFindingSource,
) -> CandidateEvidenceProjection:
    """Project one serial-peer source variant into its existing report fields."""
    if isinstance(source, UnmappedSerialPeerFindingEvidence):
        return _project_unmapped_peer(source)
    return _project_reference_review(source)


@dataclass(frozen=True, slots=True)
class SerialPeerCandidate(Candidate):
    """Serial-peer candidate retaining its typed scan and authored scope."""

    source_evidence: SerialPeerFindingSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SerialPeerFindingSource,
        *,
        subject: str,
        message: str,
    ) -> SerialPeerCandidate:
        projection = project_serial_peer_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_serial_peer_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Serial-peer fields must match their typed source projection")
