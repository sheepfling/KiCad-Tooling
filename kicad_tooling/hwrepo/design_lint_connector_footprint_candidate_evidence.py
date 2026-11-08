"""Typed connector footprint-peer sources and stable finding projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinAllOpen,
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinOpenOutlier,
)
from .connector_identity import pin_function_is_generic
from .design_lint_types import Candidate, CandidateEvidenceProjection

ConnectorFootprintPeerPinCandidateEvidence: TypeAlias = (
    ConnectorFootprintPeerPinDivergence
    | ConnectorFootprintPeerPinOpenOutlier
    | ConnectorFootprintPeerPinAllOpen
)


def project_connector_footprint_peer_pin_evidence(
    source: ConnectorFootprintPeerPinCandidateEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed footprint-peer scan record to its established report fields."""
    _require_peer_scope(source)
    evidence: dict[str, tuple[str, ...]] = {
        "value": (source.value,),
        "footprint": (source.footprint,),
        "pin_number": (source.pin_number,),
        "pin_function": (source.pin_function,),
        "assignments": _formatted_assignments(source),
    }

    if isinstance(source, ConnectorFootprintPeerPinDivergence):
        if not source.common_anchor_pin_numbers or any(
            not nets for nets in source.assignments.values()
        ):
            raise ValueError("Footprint-peer divergence requires assigned peers and an anchor")
        if len(set(source.assignments.values())) < 2:
            raise ValueError("Footprint-peer divergence requires different assignments")
        evidence.update(
            {
                "symbols": source.symbols,
                "common_anchor_pin_numbers": source.common_anchor_pin_numbers,
            }
        )
        rule_id = "connector.footprint_peer_pin_assignment_divergence"
    elif isinstance(source, ConnectorFootprintPeerPinOpenOutlier):
        if not pin_function_is_generic(source.pin_function):
            raise ValueError("Generic footprint-peer open evidence requires a generic pin function")
        expected_open_pins = tuple(pin for pin, nets in source.assignments.items() if not nets)
        if (
            not source.common_anchor_pin_numbers
            or not expected_open_pins
            or not any(source.assignments.values())
            or source.open_pins != expected_open_pins
        ):
            raise ValueError("Footprint-peer open evidence must match anchored open assignments")
        evidence.update(
            {
                "open_pins": source.open_pins,
                "symbols": source.symbols,
                "common_anchor_pin_numbers": source.common_anchor_pin_numbers,
            }
        )
        rule_id = "connector.footprint_peer_pin_open_outlier"
    else:
        if not pin_function_is_generic(source.pin_function):
            raise ValueError("Generic footprint-peer all-open evidence requires a generic pin")
        if (
            not source.assignments
            or any(source.assignments.values())
            or (not source.common_anchor_pin_numbers and source.peer_assignment_group is None)
        ):
            raise ValueError(
                "Footprint-peer all-open evidence requires open peers and an anchor or reviewed scope"
            )
        evidence.update(
            {
                "open_pins": tuple(source.assignments),
                "symbols": source.symbols,
                "common_anchor_pin_numbers": source.common_anchor_pin_numbers,
            }
        )
        rule_id = "connector.footprint_peer_pin_all_open"

    evidence.update(_peer_assignment_scope(source))
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinCandidate(Candidate):
    """Internal finding that retains its immutable footprint-peer scan record."""

    source_evidence: ConnectorFootprintPeerPinCandidateEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintPeerPinCandidateEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorFootprintPeerPinCandidate:
        projection = project_connector_footprint_peer_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_footprint_peer_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Connector footprint-peer rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Connector footprint-peer evidence must match its typed projection")


def _formatted_assignments(
    source: ConnectorFootprintPeerPinCandidateEvidence,
) -> tuple[str, ...]:
    return tuple(
        f"{pin}={','.join(nets) if nets else '<unassigned>'}"
        for pin, nets in source.assignments.items()
    )


def _peer_assignment_scope(
    source: ConnectorFootprintPeerPinCandidateEvidence,
) -> dict[str, tuple[str, ...]]:
    if (source.peer_assignment_group is None) != (not source.peer_assignment_basis):
        raise ValueError("Scoped footprint-peer findings require their reviewed basis")
    if source.peer_assignment_group is None:
        return {}
    return {
        "peer_assignment_group": (source.peer_assignment_group,),
        "peer_assignment_basis": source.peer_assignment_basis,
    }


def _require_peer_scope(source: ConnectorFootprintPeerPinCandidateEvidence) -> None:
    if not source.assignments or not source.symbols:
        raise ValueError("Footprint-peer evidence requires assignments and peer symbols")
