"""Review supported BJT bases directly connected to output-capable pins."""

from __future__ import annotations

from .component_pin_types import is_output_capable_pin_type
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.bjt_base_direct_drive"
_SUPPORTED_SYMBOLS = frozenset(
    f"transistor_bjt:q_{family}_{order}"
    for family in ("npn", "pnp")
    for order in ("bce", "bec", "cbe", "ceb", "ebc", "ecb")
)
_BJT_PIN_ROLES = {
    "b": "base",
    "base": "base",
    "c": "collector",
    "collector": "collector",
    "e": "emitter",
    "emitter": "emitter",
}


def bjts_with_direct_output_base_drive(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review exact basic BJT symbols whose base shares a net with an output pin.

    A shared native net has no intervening series resistor between the output
    pin and BJT base. This remains a review prompt because a driver may limit
    current internally or the topology may intentionally omit an external part.
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
    electrical_types = {
        pin.casefold(): kind.strip().casefold()
        for pin, kind in observed.pin_electrical_types.items()
        if kind.strip()
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
            or symbol.casefold() not in _SUPPORTED_SYMBOLS
            or len(pin_numbers) != 3
            or len({number.casefold() for number in pin_numbers}) != 3
        ):
            continue

        role_to_number: dict[str, str] = {}
        for number in pin_numbers:
            role = _BJT_PIN_ROLES.get(functions.get(f"{reference}.{number}".casefold(), ""))
            if role is None:
                continue
            if role in role_to_number:
                role_to_number.clear()
                break
            role_to_number[role] = number
        if set(role_to_number) != {"base", "collector", "emitter"}:
            continue

        base_pin = f"{reference}.{role_to_number['base']}"
        base_assignments = nets_by_pin.get(base_pin.casefold(), ())
        if len(base_assignments) != 1:
            continue
        base_net = base_assignments[0]
        output_pins = tuple(
            sorted(
                (
                    pin
                    for pin in observed.nets.get(base_net, ())
                    if pin.casefold() != base_pin.casefold()
                    and pin.rsplit(".", 1)[0].casefold() in fitted
                    and pin.rsplit(".", 1)[0].casefold() not in dnp
                    and len(nets_by_pin.get(pin.casefold(), ())) == 1
                    and is_output_capable_pin_type(electrical_types.get(pin.casefold(), ""))
                ),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        if not output_pins:
            continue

        output_pin_types = tuple(f"{pin}={electrical_types[pin.casefold()]}" for pin in output_pins)
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{base_pin}: BJT base directly shares a net with an output-capable pin",
                message=(
                    "The native netlist assigns the BJT base and output-capable pin to the same "
                    "net, with no intervening series resistor between them. Review whether the "
                    "driver provides intentional current limiting and whether the BJT base-current "
                    "requirement is met. This prompt does not establish a required resistor, "
                    "current limit, safe operating point, or physical path."
                ),
                evidence={
                    "component": (reference,),
                    "symbol": (symbol,),
                    "base_pin": (base_pin,),
                    "base_net": (base_net,),
                    "output_pins": output_pins,
                    "output_pin_types": output_pin_types,
                },
            )
        )
    return tuple(findings)
