"""Typed inputs owned by the design-lint control candidate theme."""

from __future__ import annotations

from dataclasses import dataclass

from .control_input_models import ControlInputBiasHeuristicCoverage
from .netlist_contract_models import NetlistContract


@dataclass(frozen=True, slots=True)
class ControlCandidateInputs:
    """One native observation and the resolved control-bias coverage for it."""

    observed: NetlistContract
    input_bias_coverage: ControlInputBiasHeuristicCoverage

    @classmethod
    def from_legacy_arguments(
        cls, observed: NetlistContract, coverage: ControlInputBiasHeuristicCoverage | None
    ) -> ControlCandidateInputs:
        return cls(observed, coverage or ControlInputBiasHeuristicCoverage())
