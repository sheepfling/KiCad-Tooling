"""Review explicit USB SuperSpeed endpoint functions against net labels."""

from __future__ import annotations

import re

from .bus_signal_pairs import (
    complementary_pin_function_key,
    usb_c_superspeed_lane_function_role,
    usb_ic_superspeed_lane_function_role,
)
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID = "bus.usb_c_superspeed_lane_label_mismatch"
_SUPER_SPEED_LABEL = re.compile(r"(?:usb(?:3)?(?:ss)?|ss|usbc[0-9]+)(tx|rx)([12])([pn+\-])")


def _usb_superspeed_net_label_role(net: str) -> tuple[str, str] | None:
    observed_roles: set[tuple[str, str]] = set()
    for label_part in re.split(r"[/,]", net):
        match = _SUPER_SPEED_LABEL.fullmatch(complementary_pin_function_key(label_part.strip()))
        if match is None:
            continue
        direction, lane, polarity = match.groups()
        side = "positive" if polarity in {"p", "+"} else "negative"
        observed_roles.add((f"USB SuperSpeed {direction.upper()} lane {lane}", side))
    return next(iter(observed_roles)) if len(observed_roles) == 1 else None


def usb_c_superspeed_lane_label_mismatch_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review explicit lane, direction, or polarity conflicts at USB SuperSpeed endpoints."""
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin, set()).add(net)

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for pin, function in sorted(observed.pin_functions.items()):
        reference, separator, _number = pin.rpartition(".")
        function_key = complementary_pin_function_key(function)
        if not separator or reference.casefold() in dnp_references:
            continue
        pin_role = (
            usb_c_superspeed_lane_function_role(function)
            if function_key.startswith(("stdass", "stdbss"))
            else None
        )
        if pin_role is None and is_integrated_circuit_reference(reference):
            pin_role = usb_ic_superspeed_lane_function_role(function)
        assigned_nets = nets_by_pin.get(pin, set())
        if pin_role is None or len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_role = _usb_superspeed_net_label_role(net)
        if net_role is None or net_role == pin_role:
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"Pin function identifies {pin_role[0].removeprefix('USB SuperSpeed ')} "
                    f"{pin_role[1]}, but net label {net!r} identifies {net_role[0]} {net_role[1]}. "
                    "Review the endpoint mapping and labels; neither name establishes the intended "
                    "lane assignment or routed connection."
                ),
                evidence={
                    "pin": (pin,),
                    "pin_function": (function,),
                    "pin_lane": (pin_role[0],),
                    "pin_side": (pin_role[1],),
                    "net": (net,),
                    "net_lane": (net_role[0],),
                    "net_side": (net_role[1],),
                },
            )
        )
    return tuple(findings)
