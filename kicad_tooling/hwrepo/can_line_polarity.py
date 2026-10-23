"""Review CANH/CANL pin functions against explicit CAN net names."""

from __future__ import annotations

from .bus_signal_roles import can_function_role
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "bus.can_line_polarity_label_mismatch"


def can_line_polarity_label_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find fitted CAN pins whose line function conflicts with a recognized net name."""
    pins_by_net: dict[str, set[str]] = {}
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pins_by_net.setdefault(net, set()).add(pin)
            nets_by_pin.setdefault(pin, set()).add(net)

    roles = {
        pin: role
        for pin, function in observed.pin_functions.items()
        if (role := can_function_role(function)) is not None
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for pin in sorted(roles):
        reference, separator, _number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp_references:
            continue
        pin_role = roles[pin]
        assigned_nets = nets_by_pin.get(pin, set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_role = can_function_role(net)
        if net_role is None or net_role == pin_role:
            continue

        # The complementary-pair rule already owns a same-symbol CANH/CANL short.
        same_symbol_opposite = any(
            other_pin != pin and other_pin.rpartition(".")[0] == reference and role == net_role
            for other_pin in pins_by_net.get(net, ())
            if (role := roles.get(other_pin)) is not None
        )
        if same_symbol_opposite:
            continue

        function = observed.pin_functions[pin]
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"Native CAN pin function is {pin_role}, but the assigned net name {net!r} "
                    f"identifies {net_role}. Review the endpoint pin map and line labels; names "
                    "alone do not establish bus intent or physical wiring."
                ),
                evidence={
                    "pin": (pin,),
                    "pin_function": (function,),
                    "pin_role": (pin_role,),
                    "net": (net,),
                    "net_role": (net_role,),
                },
            )
        )
    return tuple(findings)
