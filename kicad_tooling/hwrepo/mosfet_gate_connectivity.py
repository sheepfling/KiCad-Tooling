"""Review fitted three-terminal MOSFET gates with no visible peer connection."""

from __future__ import annotations

from .component_mosfet_symbols import (
    SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS,
    mosfet_terminal_role,
)
from .design_lint_mosfet_gate_candidate_evidence import (
    MOSFET_GATE_WITHOUT_PEER_RULE_ID,
    MOSFET_GATE_WITHOUT_SOURCE_BIAS_RULE_ID,
    MosfetGateCandidate,
    MosfetGateWithoutPeerEvidence,
    MosfetGateWithoutSourceBiasEvidence,
    SupportedMosfetGate,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .resistor_paths import direct_resistors

RULE_ID = MOSFET_GATE_WITHOUT_PEER_RULE_ID
SOURCE_BIAS_RULE_ID = MOSFET_GATE_WITHOUT_SOURCE_BIAS_RULE_ID


def mosfet_gates_without_peer(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find exact supported MOSFET gates with no other fitted pin on their net."""
    components = {reference.casefold() for reference in observed.components}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): pin_numbers
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    functions = {
        pin.casefold(): function.strip().casefold()
        for pin, function in observed.pin_functions.items()
    }
    native_functions = {
        pin.casefold(): function for pin, function in observed.pin_functions.items()
    }
    nets_by_pin: dict[str, list[tuple[str, str]]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), []).append((net, pin))

    findings: list[Candidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda pair: pair[0].casefold()
    ):
        reference_key = reference.casefold()
        if (
            reference_key not in components
            or reference_key in unpopulated
            or symbol.casefold() not in SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS
        ):
            continue

        pin_numbers = inventories.get(reference_key, ())
        if len(pin_numbers) != 3 or len({number.casefold() for number in pin_numbers}) != 3:
            continue
        gate_pins = tuple(
            f"{reference}.{number}"
            for number in pin_numbers
            if mosfet_terminal_role(functions.get(f"{reference}.{number}".casefold())) == "gate"
        )
        if len(gate_pins) != 1:
            continue

        gate_pin = gate_pins[0]
        assignments = nets_by_pin.get(gate_pin.casefold(), [])
        if len(assignments) > 1:
            continue
        assigned_net = assignments[0][0] if assignments else None
        peers = ()
        if assignments:
            net, _ = assignments[0]
            peers = tuple(
                sorted(
                    (
                        member
                        for member in observed.nets[net]
                        if member.casefold() != gate_pin.casefold()
                        and member.rsplit(".", 1)[0].casefold() in components
                        and member.rsplit(".", 1)[0].casefold() not in unpopulated
                    ),
                    key=str.casefold,
                )
            )
        if peers:
            continue

        device = SupportedMosfetGate(
            observed=observed,
            reference=reference,
            symbol=symbol,
            gate_pin=gate_pin,
            gate_function=native_functions[gate_pin.casefold()],
        )
        findings.append(
            MosfetGateCandidate.from_source_evidence(
                MosfetGateWithoutPeerEvidence(
                    device=device,
                    assigned_net=assigned_net,
                    other_fitted_net_members=peers,
                ),
                subject=f"{gate_pin}: MOSFET gate has no other fitted pin on its net",
                message=(
                    "This fitted, supported three-terminal MOSFET gate has no other fitted pin "
                    "assigned to the same schematic net. Review whether a control, bias, or "
                    "external interface connection is missing or intentionally absent. A peer "
                    "pin would not prove that the gate is driven, biased to a safe state, or "
                    "connected on the PCB."
                ),
            )
        )
    return tuple(findings)


def mosfet_gates_without_visible_source_bias(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review MOSFET gates with fitted peers but no visible direct source-bias resistor."""
    components = {reference.casefold() for reference in observed.components}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): pin_numbers
        for reference, pin_numbers in observed.component_pin_numbers.items()
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
    resistors = direct_resistors(observed)
    resistor_pairs = {
        frozenset((resistor.first_net.casefold(), resistor.second_net.casefold()))
        for resistor in resistors
    }

    findings: list[Candidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda pair: pair[0].casefold()
    ):
        reference_key = reference.casefold()
        if (
            reference_key not in components
            or reference_key in unpopulated
            or symbol.casefold() not in SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS
        ):
            continue
        pin_numbers = inventories.get(reference_key, ())
        if len(pin_numbers) != 3 or len({number.casefold() for number in pin_numbers}) != 3:
            continue
        gate_numbers = tuple(
            number
            for number in pin_numbers
            if mosfet_terminal_role(functions.get(f"{reference}.{number}".casefold())) == "gate"
        )
        source_numbers = tuple(
            number
            for number in pin_numbers
            if mosfet_terminal_role(functions.get(f"{reference}.{number}".casefold())) == "source"
        )
        if len(gate_numbers) != 1 or len(source_numbers) != 1:
            continue

        gate_pin = f"{reference}.{gate_numbers[0]}"
        source_pin = f"{reference}.{source_numbers[0]}"
        gate_assignments = nets_by_pin.get(gate_pin.casefold(), ())
        source_assignments = nets_by_pin.get(source_pin.casefold(), ())
        if len(gate_assignments) != 1 or len(source_assignments) != 1:
            continue
        gate_net, source_net = gate_assignments[0], source_assignments[0]
        if gate_net.casefold() == source_net.casefold():
            continue

        peers = tuple(
            sorted(
                (
                    member
                    for member in observed.nets.get(gate_net, ())
                    if member.casefold() != gate_pin.casefold()
                    and "." in member
                    and member.rsplit(".", 1)[0].casefold() in components
                    and member.rsplit(".", 1)[0].casefold() not in unpopulated
                ),
                key=str.casefold,
            )
        )
        if not peers or frozenset((gate_net.casefold(), source_net.casefold())) in resistor_pairs:
            continue

        gate_function = native_functions[gate_pin.casefold()]
        source_function = native_functions[source_pin.casefold()]
        device = SupportedMosfetGate(
            observed=observed,
            reference=reference,
            symbol=symbol,
            gate_pin=gate_pin,
            gate_function=gate_function,
        )
        findings.append(
            MosfetGateCandidate.from_source_evidence(
                MosfetGateWithoutSourceBiasEvidence(
                    device=device,
                    source_pin=source_pin,
                    source_function=source_function,
                    gate_net=gate_net,
                    source_net=source_net,
                    fitted_gate_peers=peers,
                    visible_source_bias_resistors=tuple(
                        resistor
                        for resistor in resistors
                        if frozenset(
                            (resistor.first_net.casefold(), resistor.second_net.casefold())
                        )
                        == frozenset((gate_net.casefold(), source_net.casefold()))
                    ),
                ),
                subject=f"{gate_pin}: MOSFET gate has no visible source-bias resistor",
                message=(
                    "This fitted MOSFET gate shares a net with another fitted pin, but no fitted, "
                    "nonzero two-terminal resistor is visible directly between its gate and "
                    "source nets. Review whether the driver establishes the required state when "
                    "disabled or unpowered. This prompt does not prove that a bias is required, "
                    "that a driver lacks an internal bias, or that any resistor value is adequate."
                ),
            )
        )
    return tuple(findings)
