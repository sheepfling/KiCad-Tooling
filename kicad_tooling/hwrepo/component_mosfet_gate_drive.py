"""Review supported MOSFET gates directly connected to output-capable pins."""

from __future__ import annotations

from .component_mosfet_symbols import SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS
from .component_pin_types import fitted_output_pins_on_net
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.mosfet_gate_direct_drive"
_GATE_FUNCTIONS = frozenset({"g", "gate"})
_DRAIN_FUNCTIONS = frozenset({"d", "drain"})
_SOURCE_FUNCTIONS = frozenset({"s", "source"})


def mosfets_with_direct_output_gate_drive(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review an exact supported MOSFET gate sharing a net with an output pin.

    A native net shared by the gate and output-capable pin has no visible
    series element between those pins. An external gate resistor is not always
    required, so this remains an opt-in review prompt.
    """
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions = {
        pin.casefold(): function.strip().casefold()
        for pin, function in observed.pin_functions.items()
    }
    nets_by_pin: dict[str, list[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), []).append(net)

    findings: list[Candidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference_key = reference.casefold()
        pin_numbers = inventories.get(reference_key, ())
        if (
            reference_key not in fitted
            or reference_key in dnp
            or symbol.casefold() not in SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS
            or len(pin_numbers) != 3
            or len({number.casefold() for number in pin_numbers}) != 3
        ):
            continue

        roles: dict[str, str] = {}
        for number in pin_numbers:
            function = functions.get(f"{reference}.{number}".casefold(), "")
            role = (
                "gate"
                if function in _GATE_FUNCTIONS
                else "drain"
                if function in _DRAIN_FUNCTIONS
                else "source"
                if function in _SOURCE_FUNCTIONS
                else None
            )
            if role is None or role in roles:
                roles.clear()
                break
            roles[role] = number
        if set(roles) != {"gate", "drain", "source"}:
            continue

        gate_pin = f"{reference}.{roles['gate']}"
        gate_assignments = nets_by_pin.get(gate_pin.casefold(), ())
        if len(gate_assignments) != 1:
            continue
        gate_net = gate_assignments[0]
        output_peers = fitted_output_pins_on_net(
            observed, gate_net, excluded_references=(reference,)
        )
        if not output_peers:
            continue

        output_pins = tuple(pin for pin, _ in output_peers)
        output_pin_types = tuple(f"{pin}={pin_type}" for pin, pin_type in output_peers)
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{gate_pin}: MOSFET gate directly shares a net with an output-capable pin",
                message=(
                    "The native netlist assigns this MOSFET gate and an output-capable pin to the "
                    "same net, with no visible series element between them. Review whether the "
                    "driver intentionally omits an external gate resistor for this design. This "
                    "prompt does not establish a resistor requirement, switching performance, "
                    "driver impedance, or PCB continuity."
                ),
                evidence={
                    "component": (reference,),
                    "symbol": (symbol,),
                    "gate_pin": (gate_pin,),
                    "gate_net": (gate_net,),
                    "output_pins": output_pins,
                    "output_pin_types": output_pin_types,
                },
            )
        )
    return tuple(findings)
