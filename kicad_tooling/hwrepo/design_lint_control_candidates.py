"""Translate open and insufficiently biased control-input observations."""

from __future__ import annotations

from dataclasses import dataclass

from .control_input_inventory import (
    connected_control_inputs_without_visible_rail_resistor,
    unconnected_control_inputs,
)
from .control_input_models import ControlInputBiasHeuristicCoverage
from .design_lint_control_candidate_evidence import (
    ControlCandidate,
    open_output_expected_bias_description,
)
from .design_lint_control_inputs import ControlCandidateInputs
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .open_drain_heuristics import open_output_bias_gaps


@dataclass(frozen=True, slots=True)
class ControlCandidateResult:
    """Control findings and the pin identities used by peer deduplication."""

    candidates: tuple[Candidate, ...]
    unconnected_pin_keys: frozenset[str]


def control_candidates(
    observed: NetlistContract,
    *,
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None = None,
) -> tuple[tuple[Candidate, ...], frozenset[str]]:
    """Preserve the existing tuple interface for direct callers."""
    result = scan_control_candidates(
        ControlCandidateInputs.from_legacy_arguments(observed, control_input_bias_coverage)
    )
    return result.candidates, result.unconnected_pin_keys


def scan_control_candidates(inputs: ControlCandidateInputs) -> ControlCandidateResult:
    """Build control-input findings from the theme's resolved inputs."""
    observed = inputs.observed
    found: list[Candidate] = []
    unconnected_controls = unconnected_control_inputs(observed)

    control_pin_keys = {pin.pin.casefold() for pin in unconnected_controls}

    for pin in unconnected_controls:
        found.append(
            ControlCandidate.from_source_evidence(
                source_evidence=pin,
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This recognized {pin.family} input pin has no net assignment. Review "
                    "whether it is intentionally unused, handled by internal/off-board "
                    "circuitry, or missing a connection."
                ),
            )
        )

    covered_control_nets = {
        entry.net.casefold()
        for entry in inputs.input_bias_coverage.entries
        if entry.status == "COVERED"
    }

    for gap in connected_control_inputs_without_visible_rail_resistor(observed):
        if gap.net.casefold() in covered_control_nets:
            continue
        found.append(
            ControlCandidate.from_source_evidence(
                source_evidence=gap,
                subject=f"{gap.net}: connected control input has no visible rail resistor path",
                message=(
                    "This assigned net contains a recognized reset, enable, or boot/strap input, "
                    "but no fitted conventional resistor path is visible directly or through "
                    "an unbranched series chain to a recognized positive or return net. Review "
                    "whether an internal or off-board bias, a connected driver, or another "
                    "topology establishes the intended state, and whether a local path is "
                    "required. This finding does not establish that a resistor is required."
                ),
            )
        )

    for gap in open_output_bias_gaps(observed):
        output_kind = "open-collector" if gap.bias == "pull_up" else "open-emitter"
        bias_description = open_output_expected_bias_description(gap)
        found.append(
            ControlCandidate.from_source_evidence(
                source_evidence=gap,
                subject=f"{gap.net}: {output_kind} signal has no visible local bias resistor",
                message=(
                    f"This assigned net joins a native {output_kind} output pin and a native input, "
                    f"but no fitted conventional resistor is visible for the expected {bias_description}. "
                    "Review whether an internal or off-board bias, or another topology, establishes "
                    "the intended state and whether a local resistor is required. This prompt does "
                    "not establish that a resistor is required or that any visible resistor has a "
                    "suitable value."
                ),
            )
        )
    return ControlCandidateResult(tuple(found), frozenset(control_pin_keys))
