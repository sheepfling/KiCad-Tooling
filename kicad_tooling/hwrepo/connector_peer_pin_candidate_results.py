"""Typed connector candidate outputs used by peer-pin coverage."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate

_FOOTPRINT_OPEN_OUTLIER_RULE_IDS: frozenset[DesignLintRuleId] = frozenset(
    {
        "connector.footprint_peer_pin_open_outlier",
        "connector.footprint_named_power_input_open_outlier",
        "connector.footprint_named_signal_input_open_outlier",
        "connector.footprint_named_power_output_open_outlier",
        "connector.footprint_named_signal_output_open_outlier",
        "connector.footprint_named_signal_mode_dependent_open_outlier",
        "connector.footprint_named_passive_open_outlier",
    }
)


@dataclass(frozen=True, slots=True)
class ConnectorPeerPinFindingCounts:
    """Connector findings that reconcile candidate output with peer coverage."""

    repeated_function_finding_count: int = 0
    peer_pin_outlier_finding_count: int = 0
    peer_pin_divergence_finding_count: int = 0
    generic_peer_pin_all_open_finding_count: int = 0
    part_id_peer_pin_outlier_finding_count: int = 0
    part_id_peer_pin_divergence_finding_count: int = 0
    footprint_peer_pin_divergence_finding_count: int = 0
    footprint_named_signal_divergence_finding_count: int = 0
    footprint_named_power_input_divergence_finding_count: int = 0
    footprint_named_power_input_all_open_finding_count: int = 0
    footprint_named_power_output_all_open_finding_count: int = 0
    footprint_named_signal_all_open_finding_count: int = 0
    footprint_named_power_output_divergence_finding_count: int = 0
    footprint_named_passive_divergence_finding_count: int = 0
    footprint_peer_pin_open_outlier_finding_count: int = 0
    footprint_peer_pin_all_open_finding_count: int = 0

    @classmethod
    def from_candidates(
        cls,
        candidates: Sequence[Candidate],
    ) -> ConnectorPeerPinFindingCounts:
        """Summarize connector-owned candidate findings for coverage assembly."""
        items = tuple(candidates)
        counts: Counter[DesignLintRuleId] = Counter(item.rule_id for item in items)
        return cls(
            repeated_function_finding_count=counts["connector.repeated_pin_function"],
            peer_pin_outlier_finding_count=counts["connector.peer_pin_assignment_outlier"],
            peer_pin_divergence_finding_count=counts["connector.peer_pin_assignment_divergence"],
            generic_peer_pin_all_open_finding_count=counts["connector.generic_peer_pin_all_open"],
            part_id_peer_pin_outlier_finding_count=sum(
                item.rule_id == "connector.peer_pin_assignment_outlier"
                and item.evidence.get("peer_identity_basis") == ("part_id",)
                for item in items
            ),
            part_id_peer_pin_divergence_finding_count=sum(
                item.rule_id == "connector.peer_pin_assignment_divergence"
                and item.evidence.get("peer_identity_basis") == ("part_id",)
                for item in items
            ),
            footprint_peer_pin_divergence_finding_count=counts[
                "connector.footprint_peer_pin_assignment_divergence"
            ],
            footprint_named_signal_divergence_finding_count=counts[
                "connector.footprint_named_signal_assignment_divergence"
            ],
            footprint_named_power_input_divergence_finding_count=counts[
                "connector.footprint_named_power_input_assignment_divergence"
            ],
            footprint_named_power_input_all_open_finding_count=counts[
                "connector.footprint_named_power_input_all_open"
            ],
            footprint_named_power_output_all_open_finding_count=counts[
                "connector.footprint_named_power_output_all_open"
            ],
            footprint_named_signal_all_open_finding_count=counts[
                "connector.footprint_named_signal_all_open"
            ],
            footprint_named_power_output_divergence_finding_count=counts[
                "connector.footprint_named_power_output_assignment_divergence"
            ],
            footprint_named_passive_divergence_finding_count=counts[
                "connector.footprint_named_passive_assignment_divergence"
            ],
            footprint_peer_pin_open_outlier_finding_count=sum(
                item.rule_id in _FOOTPRINT_OPEN_OUTLIER_RULE_IDS for item in items
            ),
            footprint_peer_pin_all_open_finding_count=counts[
                "connector.footprint_peer_pin_all_open"
            ],
        )


@dataclass(frozen=True, slots=True)
class ConnectorCandidateResult:
    """Connector findings and their coverage-reconciliation data."""

    candidates: tuple[Candidate, ...]
    peer_pin_finding_counts: ConnectorPeerPinFindingCounts

    def __post_init__(self) -> None:
        expected = ConnectorPeerPinFindingCounts.from_candidates(self.candidates)
        if self.peer_pin_finding_counts != expected:
            raise ValueError("Connector finding counts must match connector candidates")
