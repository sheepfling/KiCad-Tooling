"""Review supported MOSFET gates directly connected to output-capable pins."""

from __future__ import annotations

from .component_mosfet_symbols import (
    SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS,
    mosfet_terminal_role,
)
from .component_pin_types import fitted_output_pins_on_net
from .design_lint_mosfet_gate_candidate_evidence import (
    MOSFET_GATE_DIRECT_DRIVE_RULE_ID,
    MosfetGateCandidate,
    MosfetGateDirectDriveEvidence,
    SupportedMosfetGate,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID = MOSFET_GATE_DIRECT_DRIVE_RULE_ID


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
    native_functions = {
        pin.casefold(): function for pin, function in observed.pin_functions.items()
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
            role = mosfet_terminal_role(function)
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
        device = SupportedMosfetGate(
            observed=observed,
            reference=reference,
            symbol=symbol,
            gate_pin=gate_pin,
            gate_function=native_functions[gate_pin.casefold()],
        )
        findings.append(
            MosfetGateCandidate.from_source_evidence(
                MosfetGateDirectDriveEvidence(
                    device=device,
                    drain_pin=f"{reference}.{roles['drain']}",
                    source_pin=f"{reference}.{roles['source']}",
                    gate_net=gate_net,
                    output_pins=output_pins,
                    output_pin_types=output_pin_types,
                ),
                subject=f"{gate_pin}: MOSFET gate directly shares a net with an output-capable pin",
                message=(
                    "The native netlist assigns this MOSFET gate and an output-capable pin to the "
                    "same net, with no visible series element between them. Review whether the "
                    "driver intentionally omits an external gate resistor for this design. This "
                    "prompt does not establish a resistor requirement, switching performance, "
                    "driver impedance, or PCB continuity."
                ),
            )
        )
    return tuple(findings)
