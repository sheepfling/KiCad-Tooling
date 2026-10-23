"""Review supported BJT bases directly connected to output-capable pins."""

from __future__ import annotations

from .component_bjt_symbols import basic_bjt_role_numbers
from .component_pin_types import fitted_output_pins_on_net
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.bjt_base_direct_drive"


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
        if reference_key not in fitted or reference_key in dnp:
            continue
        role_to_number = basic_bjt_role_numbers(reference, symbol, pin_numbers, functions)
        if role_to_number is None:
            continue

        base_pin = f"{reference}.{role_to_number['base']}"
        base_assignments = nets_by_pin.get(base_pin.casefold(), ())
        if len(base_assignments) != 1:
            continue
        base_net = base_assignments[0]
        output_peers = fitted_output_pins_on_net(
            observed, base_net, excluded_references=(reference,)
        )
        if not output_peers:
            continue

        output_pins = tuple(pin for pin, _ in output_peers)
        output_pin_types = tuple(f"{pin}={pin_type}" for pin, pin_type in output_peers)
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
