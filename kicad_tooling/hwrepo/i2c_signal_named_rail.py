"""Review I2C controller signal pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_roles import i2c_signal_role
from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_roles import named_rail_role_clue

RULE_ID: DesignLintRuleId = "bus.i2c_signal_on_named_rail"


def i2c_signal_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review a fitted IC's explicit SDA/SCL pin when assigned directly to a named rail.

    The pin function and net label are review clues. This check does not infer
    that the rail connection is wrong or that the I2C endpoint is required.
    """
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    functions_by_pin: dict[str, list[tuple[str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        functions_by_pin.setdefault(pin.casefold(), []).append((pin, function))

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    candidates: list[Candidate] = []
    for folded_pin, entries in sorted(functions_by_pin.items()):
        if len(entries) != 1:
            continue
        pin, function = entries[0]
        reference, separator, number = pin.rpartition(".")
        if (
            not separator
            or not is_integrated_circuit_reference(reference)
            or reference.casefold() in dnp_references
            or lookup_unique_casefold(observed.components, reference) is None
        ):
            continue

        pin_role = i2c_signal_role(function)
        if pin_role is None:
            continue
        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if inventory is None:
            continue
        inventory_keys = {item.casefold() for item in inventory}
        if len(inventory_keys) != len(inventory) or number.casefold() not in inventory_keys:
            continue

        assigned_nets = nets_by_pin.get(folded_pin, set())
        if len(assigned_nets) != 1:
            continue
        net_name = next(iter(assigned_nets))
        label_role = named_rail_role_clue(net_name)
        if label_role is None:
            continue

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: {function} on {label_role} net {net_name}",
                message=(
                    f"The native I2C pin function is {pin_role}, while its single assigned "
                    f"net label ({net_name!r}) is recognized as {label_role}. Review whether "
                    "this is an intentional rail strap or a pin-assignment issue. The function "
                    "and label are review clues, not proof of electrical potential, required "
                    "bus membership, or a defect; this check does not assess PCB copper or "
                    "physical continuity."
                ),
                evidence={
                    "pin": (pin,),
                    "pin_function": (function,),
                    "pin_role": (pin_role,),
                    "assigned_net": (net_name,),
                    "net_label_role_clue": (label_role,),
                    "component_pin_inventory": tuple(sorted(inventory_keys)),
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
