"""Typed component-peer candidate inputs and coverage summaries."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import assert_never

from .component_peer_pin_models import ComponentPeerPinRuleId
from .component_peer_pin_scan import ComponentPeerPinAssignmentScans
from .design_lint_types import Candidate
from .models import NetlistContract


@dataclass(frozen=True, slots=True)
class ComponentPeerCandidateInputs:
    """Native observation and cross-theme keys required for peer-pin findings."""

    observed: NetlistContract
    peer_pin_scans: ComponentPeerPinAssignmentScans
    reviewed_connector_references: tuple[str, ...]
    control_pin_keys: frozenset[str]


@dataclass(frozen=True, slots=True)
class ComponentPeerPinFindingCounts:
    """Counts of component-peer findings used by source-bound coverage."""

    power_output_unconnected: int = 0
    signal_output_unconnected: int = 0
    signal_input_unconnected: int = 0
    bidirectional_pin_unconnected: int = 0
    power_input_assignment_divergence: int = 0
    power_input_named_assignment_divergence: int = 0
    power_input_named_all_open: int = 0
    power_input_open_assignment: int = 0
    generic_peer_pin_mixed_open: int = 0
    generic_peer_pin_all_open: int = 0
    generic_peer_pin_assignment_outlier: int = 0

    @classmethod
    def from_candidates(cls, candidates: Sequence[Candidate]) -> ComponentPeerPinFindingCounts:
        counts: Counter[str] = Counter(item.rule_id for item in candidates)
        return cls(
            power_output_unconnected=counts["component.peer_power_output_unconnected"],
            signal_output_unconnected=counts["component.peer_signal_output_unconnected"],
            signal_input_unconnected=counts["component.peer_signal_input_unconnected"],
            bidirectional_pin_unconnected=counts["component.peer_bidirectional_pin_unconnected"],
            power_input_assignment_divergence=counts[
                "component.peer_power_input_assignment_divergence"
            ],
            power_input_named_assignment_divergence=counts[
                "component.peer_power_input_named_assignment_divergence"
            ],
            power_input_named_all_open=counts["component.peer_power_input_named_all_open"],
            power_input_open_assignment=counts["component.peer_power_input_open_assignment"],
            generic_peer_pin_mixed_open=counts["component.generic_peer_pin_mixed_open"],
            generic_peer_pin_all_open=counts["component.generic_peer_pin_all_open"],
            generic_peer_pin_assignment_outlier=counts[
                "component.generic_peer_pin_assignment_outlier"
            ],
        )

    def for_rule(self, rule_id: ComponentPeerPinRuleId) -> int:
        match rule_id:
            case "component.peer_power_output_unconnected":
                return self.power_output_unconnected
            case "component.peer_signal_output_unconnected":
                return self.signal_output_unconnected
            case "component.peer_signal_input_unconnected":
                return self.signal_input_unconnected
            case "component.peer_bidirectional_pin_unconnected":
                return self.bidirectional_pin_unconnected
            case "component.peer_power_input_assignment_divergence":
                return self.power_input_assignment_divergence
            case "component.peer_power_input_named_assignment_divergence":
                return self.power_input_named_assignment_divergence
            case "component.peer_power_input_named_all_open":
                return self.power_input_named_all_open
            case "component.peer_power_input_open_assignment":
                return self.power_input_open_assignment
            case "component.generic_peer_pin_mixed_open":
                return self.generic_peer_pin_mixed_open
            case "component.generic_peer_pin_all_open":
                return self.generic_peer_pin_all_open
            case "component.generic_peer_pin_assignment_outlier":
                return self.generic_peer_pin_assignment_outlier
            case _ as unreachable:
                assert_never(unreachable)


@dataclass(frozen=True, slots=True)
class ComponentPeerCandidateResult:
    """Component-peer findings and the counts needed by coverage assembly."""

    candidates: tuple[Candidate, ...]
    finding_counts: ComponentPeerPinFindingCounts

    def __post_init__(self) -> None:
        expected = ComponentPeerPinFindingCounts.from_candidates(self.candidates)
        if self.finding_counts != expected:
            raise ValueError("Component peer finding counts must match theme candidates")
