"""Opt-in BJT collector/emitter order review from named rail evidence."""

from __future__ import annotations

from .component_rail_potentials import named_net_potential, potential_is_lower
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.bjt_terminal_order_on_named_rails"
_SUPPORTED_SYMBOLS = frozenset(
    f"transistor_bjt:q_{family}_{order}"
    for family in ("npn", "pnp")
    for order in ("bce", "bec", "cbe", "ceb", "ebc", "ecb")
)
_TERMINAL_FUNCTIONS = {
    "b": "base",
    "c": "collector",
    "e": "emitter",
}


def bjts_with_unusual_collector_emitter_rail_order(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
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
        normalized_symbol = symbol.casefold()
        pin_numbers = inventories.get(reference_key, ())
        if (
            reference_key not in fitted
            or reference_key in dnp
            or normalized_symbol not in _SUPPORTED_SYMBOLS
            or len(pin_numbers) != 3
            or len({number.casefold() for number in pin_numbers}) != 3
        ):
            continue

        role_to_number: dict[str, str] = {}
        duplicate_role = False
        for number in pin_numbers:
            role = _TERMINAL_FUNCTIONS.get(functions.get(f"{reference}.{number}".casefold(), ""))
            if role is None:
                continue
            if role in role_to_number:
                duplicate_role = True
                break
            role_to_number[role] = number
        if duplicate_role or set(role_to_number) != {"base", "collector", "emitter"}:
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
            expected_lower, observed_lower = "emitter", "collector"
            description = "NPN collector resolves below its emitter"
        else:
            unusual_order = potential_is_lower(emitter_potential, collector_potential)
            expected_lower, observed_lower = "collector", "emitter"
            description = "PNP emitter resolves below its collector"
        if not unusual_order:
            continue

        evidence: dict[str, tuple[str, ...]] = {
            "component": (reference,),
            "symbol": (symbol,),
            "transistor_family": (family,),
            "collector_pin": (collector_pin,),
            "collector_net": (collector_net,),
            "collector_potential_basis": collector_potential.evidence,
            "emitter_pin": (emitter_pin,),
            "emitter_net": (emitter_net,),
            "emitter_potential_basis": emitter_potential.evidence,
            "expected_lower_terminal": (expected_lower,),
            "observed_lower_terminal": (observed_lower,),
        }
        if collector_potential.value is not None:
            evidence["collector_ordering_value_volts"] = (str(collector_potential.value),)
        if emitter_potential.value is not None:
            evidence["emitter_ordering_value_volts"] = (str(emitter_potential.value),)

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: {family.upper()} transistor collector/emitter order merits review",
                message=(
                    f"{description} based on named rail evidence. Review the exact symbol-to-footprint "
                    "pin map and intended operating topology. Conventional order is not a requirement "
                    "for every circuit; rail labels do not prove measured voltage, physical pin mapping, "
                    "or intended current direction."
                ),
                evidence=evidence,
            )
        )
    return tuple(findings)
