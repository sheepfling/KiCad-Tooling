"""Compatibility facade for project-authored control-input analysis."""

from __future__ import annotations

from .control_input_bias import control_input_bias_heuristic_coverage
from .control_input_checks import control_input_checks
from .control_input_inventory import (
    ConnectedControlInput,
    ControlInputBiasGap,
    UnconnectedControlInput,
    connected_control_inputs_without_visible_rail_resistor,
    control_input_family,
    unconnected_control_inputs,
)

__all__ = [
    "ConnectedControlInput",
    "ControlInputBiasGap",
    "UnconnectedControlInput",
    "connected_control_inputs_without_visible_rail_resistor",
    "control_input_bias_heuristic_coverage",
    "control_input_checks",
    "control_input_family",
    "unconnected_control_inputs",
]
