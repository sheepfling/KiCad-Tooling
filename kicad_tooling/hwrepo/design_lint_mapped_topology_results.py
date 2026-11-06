"""Typed cross-theme finding counts for authored mapped-topology checks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .design_lint_types import Candidate


@dataclass(frozen=True, slots=True)
class MappedTopologyFindingCounts:
    """Per-owner finding counts used to assemble mapped-check execution runs."""

    usb_data_path_mismatch: int = 0
    power_series_path_mismatch: int = 0
    power_sequence_dependency_mismatch: int = 0
    oscillator_output_path_mismatch: int = 0
    led_current_range_mismatch: int = 0

    @classmethod
    def from_candidates(cls, candidates: Sequence[Candidate]) -> MappedTopologyFindingCounts:
        """Count final findings only to verify that theme summaries agree."""
        return cls(
            usb_data_path_mismatch=sum(
                item.rule_id == "bus.usb_data_path_mismatch" for item in candidates
            ),
            power_series_path_mismatch=sum(
                item.rule_id == "power.mapped_series_path_mismatch" for item in candidates
            ),
            power_sequence_dependency_mismatch=sum(
                item.rule_id == "power.mapped_sequence_dependency_mismatch" for item in candidates
            ),
            oscillator_output_path_mismatch=sum(
                item.rule_id == "oscillator.output_load_path_mismatch" for item in candidates
            ),
            led_current_range_mismatch=sum(
                item.rule_id == "component.mapped_led_current_range_mismatch" for item in candidates
            ),
        )
