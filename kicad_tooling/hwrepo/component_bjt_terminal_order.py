"""Opt-in BJT collector/emitter order review from named rail evidence."""

from __future__ import annotations

from .component_bjt_symbols import basic_bjt_role_numbers
from .component_named_rail_terminal import (
    NamedRailTerminalEvidence,
    normalized_pin_function_index,
)
from .component_rail_potentials import named_net_potential, potential_is_lower
from .design_lint_component_terminal_order_candidate_evidence import (
    BJT_TERMINAL_ORDER_RULE_ID,
    BjtTerminalOrderEvidence,
    ComponentTerminalOrderCandidate,
)
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_assignments

RULE_ID = BJT_TERMINAL_ORDER_RULE_ID


def bjts_with_unusual_collector_emitter_rail_order(
    observed: NetlistContract,
) -> tuple[ComponentTerminalOrderCandidate, ...]:
    """Review supported BJTs whose named rails reverse conventional C/E order.

    Basic NPN symbols conventionally place the emitter below the collector;
    basic PNP symbols conventionally place the collector below the emitter.
    Reverse-active, switching, and other valid circuits can intentionally use
    the opposite relationship, so this rule is configurable and default-off.
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
        normalized_symbol = symbol.casefold()
        pin_numbers = inventories.get(reference_key, ())
        if reference_key not in fitted or reference_key in dnp:
            continue
        role_to_number = basic_bjt_role_numbers(reference, symbol, pin_numbers, functions)
        if role_to_number is None:
            continue

        collector_pin = f"{reference}.{role_to_number['collector']}"
        emitter_pin = f"{reference}.{role_to_number['emitter']}"
        collector_assignments = nets_by_pin.get(collector_pin.casefold(), ())
        emitter_assignments = nets_by_pin.get(emitter_pin.casefold(), ())
        if len(collector_assignments) != 1 or len(emitter_assignments) != 1:
            continue
        collector_net, emitter_net = collector_assignments[0], emitter_assignments[0]
        if collector_net.casefold() == emitter_net.casefold():
            continue

        collector_potential = named_net_potential(
            collector_net, observed.nets[collector_net], functions
        )
        emitter_potential = named_net_potential(emitter_net, observed.nets[emitter_net], functions)
        if collector_potential is None or emitter_potential is None:
            continue

        family = "npn" if "q_npn_" in normalized_symbol else "pnp"
        if family == "npn":
            unusual_order = potential_is_lower(collector_potential, emitter_potential)
            description = "NPN collector resolves below its emitter"
        else:
            unusual_order = potential_is_lower(emitter_potential, collector_potential)
            description = "PNP emitter resolves below its collector"
        if not unusual_order:
            continue

        findings.append(
            ComponentTerminalOrderCandidate.from_source_evidence(
                BjtTerminalOrderEvidence(
                    observed=observed,
                    reference=reference,
                    symbol=symbol,
                    family=family,
                    collector=NamedRailTerminalEvidence(
                        pin=collector_pin,
                        net=collector_net,
                        potential=collector_potential,
                    ),
                    emitter=NamedRailTerminalEvidence(
                        pin=emitter_pin,
                        net=emitter_net,
                        potential=emitter_potential,
                    ),
                ),
                subject=f"{reference}: {family.upper()} transistor collector/emitter order merits review",
                message=(
                    f"{description} based on named rail evidence. Review the exact symbol-to-footprint "
                    "pin map and intended operating topology. Conventional order is not a requirement "
                    "for every circuit; rail labels do not prove measured voltage, physical pin mapping, "
                    "or intended current direction."
                ),
            )
        )
    return tuple(findings)
