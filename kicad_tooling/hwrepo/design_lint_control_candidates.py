"""Translate open and insufficiently biased control-input observations."""

from __future__ import annotations

from .control_input_inventory import (
    connected_control_inputs_without_visible_rail_resistor,
    unconnected_control_inputs,
)
from .design_lint_types import Candidate
from .models import ControlInputBiasHeuristicCoverage, NetlistContract
from .open_drain_heuristics import open_output_bias_gaps


def control_candidates(
    observed: NetlistContract,
    *,
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None = None,
) -> tuple[tuple[Candidate, ...], frozenset[str]]:
    """Build control-input findings and the pin keys used to avoid duplicate prompts."""
    found: list[Candidate] = []
    unconnected_controls = unconnected_control_inputs(observed)

    control_pin_keys = {pin.pin.casefold() for pin in unconnected_controls}

    for pin in unconnected_controls:
        found.append(
            Candidate(
                rule_id="control.unconnected_control_input",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This recognized {pin.family} input pin has no net assignment. Review "
                    "whether it is intentionally unused, handled by internal/off-board "
                    "circuitry, or missing a connection."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "family": (pin.family,),
                    "electrical_type": (pin.electrical_type,),
                },
            )
        )

    covered_control_nets = {
        entry.net.casefold()
        for entry in (
            () if control_input_bias_coverage is None else control_input_bias_coverage.entries
        )
        if entry.status == "COVERED"
    }

    for gap in connected_control_inputs_without_visible_rail_resistor(observed):
        if gap.net.casefold() in covered_control_nets:
            continue
        controls = tuple(
            f"{control.pin}: {control.function} ({control.family}, {control.electrical_type})"
            for control in gap.controls
        )
        found.append(
            Candidate(
                rule_id="control.connected_control_input_without_visible_bias",
                subject=f"{gap.net}: connected control input has no visible rail resistor",
                message=(
                    "This assigned net contains a recognized reset, enable, or boot/strap input, "
                    "but no fitted conventional resistor is directly visible between the net "
                    "and a recognized positive or return net. Review whether an internal or "
                    "off-board bias, a connected driver, or another topology establishes the "
                    "intended state, and whether a local path is required. This finding does "
                    "not establish that a resistor is required."
                ),
                evidence={
                    "net": (gap.net,),
                    "control_inputs": controls,
                    "output_capable_peers": gap.output_capable_peers,
                },
            )
        )

    for gap in open_output_bias_gaps(observed):
        bias_description = (
            "pull-up to a recognized positive rail"
            if gap.bias == "pull_up"
            else "pull-down to a recognized return"
        )
        output_kind = "open-collector" if gap.bias == "pull_up" else "open-emitter"
        found.append(
            Candidate(
                rule_id=(
                    "signal.open_collector_input_without_visible_bias"
                    if gap.bias == "pull_up"
                    else "signal.open_emitter_input_without_visible_bias"
                ),
                subject=f"{gap.net}: {output_kind} signal has no visible local bias resistor",
                message=(
                    f"This assigned net joins a native {output_kind} output pin and a native input, "
                    f"but no fitted conventional resistor is visible for the expected {bias_description}. "
                    "Review whether an internal or off-board bias, or another topology, establishes "
                    "the intended state and whether a local resistor is required. This prompt does "
                    "not establish that a resistor is required or that any visible resistor has a "
                    "suitable value."
                ),
                evidence={
                    "net": (gap.net,),
                    "expected_bias": (bias_description,),
                    "open_output_pins": gap.output_pins,
                    "input_pins": gap.input_pins,
                    "visible_resistors_on_signal_net": gap.visible_resistors,
                },
            )
        )
    return tuple(found), frozenset(control_pin_keys)
