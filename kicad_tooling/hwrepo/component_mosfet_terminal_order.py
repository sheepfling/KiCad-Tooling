"""Opt-in MOSFET drain/source order review from explicit rail evidence."""

from __future__ import annotations

from .component_mosfet_symbols import mosfet_channel_type
from .component_rail_potentials import named_net_potential, potential_is_lower
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.mosfet_terminal_order_on_named_rails"
_TERMINAL_FUNCTIONS = {
    "d": "drain",
    "drain": "drain",
    "g": "gate",
    "gate": "gate",
    "s": "source",
    "source": "source",
}


def mosfets_with_unusual_drain_source_rail_order(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
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
    functions = {
        pin.casefold(): function.strip().casefold()
        for pin, function in observed.pin_functions.items()
        if function.strip()
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

        role_to_number: dict[str, str] = {}
        for number in pin_numbers:
            role = _TERMINAL_FUNCTIONS.get(functions.get(f"{reference}.{number}".casefold(), ""))
            if role is None:
                continue
            if role in role_to_number:
                role_to_number.clear()
                break
            role_to_number[role] = number
        if set(role_to_number) != {"drain", "gate", "source"}:
            continue

        drain_pin = f"{reference}.{role_to_number['drain']}"
        source_pin = f"{reference}.{role_to_number['source']}"
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
            expected_lower, observed_lower = "source", "drain"
            unexpected_description = "NMOS drain resolves below its source"
        else:
            reversed_order = potential_is_lower(source_potential, drain_potential)
            expected_lower, observed_lower = "drain", "source"
            unexpected_description = "PMOS source resolves below its drain"
        if not reversed_order:
            continue

        evidence: dict[str, tuple[str, ...]] = {
            "component": (reference,),
            "symbol": (symbol,),
            "channel_type": (channel_type,),
            "drain_pin": (drain_pin,),
            "drain_net": (drain_net,),
            "drain_potential_basis": drain_potential.evidence,
            "source_pin": (source_pin,),
            "source_net": (source_net,),
            "source_potential_basis": source_potential.evidence,
            "expected_lower_terminal": (expected_lower,),
            "observed_lower_terminal": (observed_lower,),
        }
        if drain_potential.value is not None:
            evidence["drain_ordering_value_volts"] = (str(drain_potential.value),)
        if source_potential.value is not None:
            evidence["source_ordering_value_volts"] = (str(source_potential.value),)

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: MOSFET {channel_type.upper()} drain/source order merits review",
                message=(
                    f"{unexpected_description} based on named rail evidence. Review the exact "
                    "symbol-to-footprint pin map and intended current or reverse-current "
                    "behavior. The conventional order is not a requirement for every topology, "
                    "and net names do not establish measured voltage or physical pin mapping."
                ),
                evidence=evidence,
            )
        )
    return tuple(findings)
