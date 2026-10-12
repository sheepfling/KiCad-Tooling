"""Review named positive-supply pins assigned to explicitly negative rails."""

from __future__ import annotations

from .connector_identity import power_function_key
from .design_lint_types import Candidate
from .models import NetlistContract
from .power_rails import negative_voltage_rail_key


def positive_supply_pins_on_negative_rails(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Prompt review for a named supply pin assigned to an explicitly minus-prefixed rail."""
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    candidates: list[Candidate] = []
    for pin, function in sorted(observed.pin_functions.items()):
        reference = pin.rsplit(".", 1)[0]
        if reference.startswith("#") or reference.casefold() in dnp:
            continue
        function_key = power_function_key(function)
        assigned_nets = nets_by_pin.get(pin.casefold(), set())
        if function_key is None or len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        negative_rail_key = negative_voltage_rail_key(net)
        if negative_rail_key is None:
            continue
        candidates.append(
            Candidate(
                rule_id="power.named_supply_pin_on_negative_rail",
                subject=f"{pin}: {function} pin assigned to {net}",
                message=(
                    "This named supply pin is assigned to a net whose label has an explicit "
                    "negative-voltage form. Review the symbol pinout and the rail naming; "
                    "these names do not prove electrical potential or project intent."
                ),
                evidence={
                    pin: (f"native_function={function}", f"supply_function_key={function_key}"),
                    "assigned_net": (net,),
                    "negative_rail_key": (negative_rail_key,),
                },
            )
        )
    return tuple(candidates)
