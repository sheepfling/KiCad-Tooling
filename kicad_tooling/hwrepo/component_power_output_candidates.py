"""Review candidates for generic component power-output pins left open."""

from __future__ import annotations

from .component_pin_patterns import unconnected_generic_power_output_component_pins
from .design_lint_types import Candidate
from .models import NetlistContract


def unconnected_power_output_candidates(
    observed: NetlistContract,
    *,
    declared_connector_references: tuple[str, ...] = (),
    peer_unconnected_pins: frozenset[str] = frozenset(),
) -> tuple[Candidate, ...]:
    """Prompt review for generic open outputs not already covered by peer checks."""
    peer_open_pins = {pin.casefold() for pin in peer_unconnected_pins}
    findings: list[Candidate] = []
    for pin in unconnected_generic_power_output_component_pins(
        observed, declared_connector_references
    ):
        if pin.pin.casefold() in peer_open_pins:
            continue
        evidence = {
            "symbol": (pin.symbol,),
            "pin_electrical_type": (pin.electrical_type,),
            pin.pin: (),
        }
        if pin.function is not None:
            evidence["native_pin_function"] = (pin.function,)
        findings.append(
            Candidate(
                rule_id="component.unconnected_power_output",
                subject=f"{pin.pin}: generic native power-output pin is unassigned",
                message=(
                    "KiCad's native symbol metadata classifies this generic component pin as "
                    "power_out, but the exported netlist assigns it to no net. Review whether "
                    "the pin is intentionally open or a power-output connection is missing. "
                    "The electrical type does not identify the pin's specific role or require "
                    "it to be connected."
                ),
                evidence=evidence,
            )
        )
    return tuple(findings)
