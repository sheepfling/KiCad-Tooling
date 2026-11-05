"""Opt-in MOSFET drain/source order review from explicit rail evidence."""

from __future__ import annotations

from .component_mosfet_symbols import mosfet_channel_type, mosfet_terminal_role_numbers
from .component_named_rail_terminal import (
    NamedRailTerminalEvidence,
    normalized_pin_function_index,
)
from .component_rail_potentials import named_net_potential, potential_is_lower
from .design_lint_component_terminal_order_candidate_evidence import (
    MOSFET_TERMINAL_ORDER_RULE_ID,
    ComponentTerminalOrderCandidate,
    MosfetTerminalOrderEvidence,
)
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_assignments

RULE_ID = MOSFET_TERMINAL_ORDER_RULE_ID


def mosfets_with_unusual_drain_source_rail_order(
    observed: NetlistContract,
) -> tuple[ComponentTerminalOrderCandidate, ...]:
    """Review a supported MOSFET when named rails reverse conventional D/S order.

    NMOS symbols conventionally place the source below the drain; PMOS symbols
    conventionally place the drain below the source. The prompt is deliberately
    default-off because reverse-current control, back-to-back switches, and
    other valid topologies can use a different orientation.
    """
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions = normalized_pin_function_index(observed)
    nets_by_pin = netlist_pin_net_assignments(observed)

    findings: list[ComponentTerminalOrderCandidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference_key = reference.casefold()
        channel_type = mosfet_channel_type(symbol)
        pin_numbers = inventories.get(reference_key, ())
        if (
            reference_key not in fitted
            or reference_key in dnp
            or channel_type is None
            or len(pin_numbers) != 3
            or len({number.casefold() for number in pin_numbers}) != 3
        ):
            continue

        role_to_number = mosfet_terminal_role_numbers(
            reference, symbol, pin_numbers, observed.pin_functions
        )
        if role_to_number is None:
            continue

        drain_pin = f"{reference}.{role_to_number.drain}"
        source_pin = f"{reference}.{role_to_number.source}"
        drain_assignments = nets_by_pin.get(drain_pin.casefold(), ())
        source_assignments = nets_by_pin.get(source_pin.casefold(), ())
        if len(drain_assignments) != 1 or len(source_assignments) != 1:
            continue
        drain_net, source_net = drain_assignments[0], source_assignments[0]
        if drain_net.casefold() == source_net.casefold():
            continue

        drain_potential = named_net_potential(drain_net, observed.nets[drain_net], functions)
        source_potential = named_net_potential(source_net, observed.nets[source_net], functions)
        if drain_potential is None or source_potential is None:
            continue

        if channel_type == "nmos":
            reversed_order = potential_is_lower(drain_potential, source_potential)
            unexpected_description = "NMOS drain resolves below its source"
        else:
            reversed_order = potential_is_lower(source_potential, drain_potential)
            unexpected_description = "PMOS source resolves below its drain"
        if not reversed_order:
            continue

        findings.append(
            ComponentTerminalOrderCandidate.from_source_evidence(
                MosfetTerminalOrderEvidence(
                    observed=observed,
                    reference=reference,
                    symbol=symbol,
                    channel_type=channel_type,
                    drain=NamedRailTerminalEvidence(
                        pin=drain_pin,
                        net=drain_net,
                        potential=drain_potential,
                    ),
                    source=NamedRailTerminalEvidence(
                        pin=source_pin,
                        net=source_net,
                        potential=source_potential,
                    ),
                ),
                subject=f"{reference}: MOSFET {channel_type.upper()} drain/source order merits review",
                message=(
                    f"{unexpected_description} based on named rail evidence. Review the exact "
                    "symbol-to-footprint pin map and intended current or reverse-current "
                    "behavior. The conventional order is not a requirement for every topology, "
                    "and net names do not establish measured voltage or physical pin mapping."
                ),
            )
        )
    return tuple(findings)
