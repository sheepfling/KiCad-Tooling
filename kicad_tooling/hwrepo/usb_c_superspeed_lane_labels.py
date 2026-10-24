"""Review explicit USB-C SuperSpeed connector functions against net labels."""

from __future__ import annotations

import re

from .bus_signal_pairs import (
    complementary_pin_function_key,
    usb_c_superspeed_lane_function_role,
)
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "bus.usb_c_superspeed_lane_label_mismatch"
_SUPER_SPEED_LABEL = re.compile(r"(?:usb(?:3)?(?:ss)?|ss)(tx|rx)([12])([pn+\-])")


def _usb_c_superspeed_net_label_role(net: str) -> tuple[str, str] | None:
    match = _SUPER_SPEED_LABEL.fullmatch(complementary_pin_function_key(net))
    if match is None:
        return None
    direction, lane, polarity = match.groups()
    side = "positive" if polarity in {"p", "+"} else "negative"
    return f"USB SuperSpeed {direction.upper()} lane {lane}", side


def usb_c_superspeed_lane_label_mismatch_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review explicit lane, direction, or polarity label conflicts on USB-C pins."""
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin, set()).add(net)

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for pin, function in sorted(observed.pin_functions.items()):
        reference, separator, _number = pin.rpartition(".")
        function_key = complementary_pin_function_key(function)
        if (
            not separator
            or reference.casefold() in dnp_references
            or not function_key.startswith(("stdass", "stdbss"))
        ):
            continue
        pin_role = usb_c_superspeed_lane_function_role(function)
        assigned_nets = nets_by_pin.get(pin, set())
        if pin_role is None or len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_role = _usb_c_superspeed_net_label_role(net)
        if net_role is None or net_role == pin_role:
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"Native USB-C SuperSpeed pin function identifies {pin_role[0]} {pin_role[1]}, "
                    f"but assigned net name {net!r} identifies {net_role[0]} {net_role[1]}. "
                    "Review the connector mapping and labels; neither name establishes the intended "
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
