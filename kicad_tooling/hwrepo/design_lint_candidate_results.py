"""Typed results returned by staged design-lint candidate scanning."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_peer_pin_candidate_results import ConnectorPeerPinFindingCounts
from .design_lint_types import Candidate
from .peer_reference_candidate_keys import PeerReferenceCandidateKeys


@dataclass(frozen=True, slots=True)
class DesignLintCandidateScanResult:
    """Findings plus the theme-derived identities required by later coverage."""

    candidates: tuple[Candidate, ...]
    peer_reference_keys: PeerReferenceCandidateKeys
    connector_peer_pin_finding_counts: ConnectorPeerPinFindingCounts

    def __post_init__(self) -> None:
        expected = PeerReferenceCandidateKeys.from_candidates(self.candidates)
        if self.peer_reference_keys != expected:
            raise ValueError("Candidate scan peer keys must match typed candidate identities")
        connector_counts = ConnectorPeerPinFindingCounts.from_candidates(self.candidates)
        if self.connector_peer_pin_finding_counts != connector_counts:
            raise ValueError("Candidate scan connector counts must match typed candidates")
