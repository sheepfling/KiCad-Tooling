"""Review Ethernet pair pin functions against explicit net-label roles."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .bus_signal_pairs import (
    complementary_pin_function_key,
    ethernet_data_pair_function_role,
    ethernet_management_function_role,
)
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "bus.ethernet_data_label_mismatch"
MANAGEMENT_RULE_ID = "bus.ethernet_management_label_mismatch"

_ETHERNET_NET_LABEL_ROLES: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "td+": ("TX", "positive"),
        "td-": ("TX", "negative"),
        "tdp": ("TX", "positive"),
        "tdn": ("TX", "negative"),
        "tx+": ("TX", "positive"),
        "tx-": ("TX", "negative"),
        "txp": ("TX", "positive"),
        "txn": ("TX", "negative"),
        "rd+": ("RX", "positive"),
        "rd-": ("RX", "negative"),
        "rdp": ("RX", "positive"),
        "rdn": ("RX", "negative"),
        "rx+": ("RX", "positive"),
        "rx-": ("RX", "negative"),
        "rxp": ("RX", "positive"),
        "rxn": ("RX", "negative"),
    }
)
_ETHERNET_NET_LABEL_PREFIXES = ("ethernet", "eth", "mdi")
_ETHERNET_MANAGEMENT_NET_LABEL_PREFIXES = ("ethernet", "eth", "smi")


def _ethernet_net_label_key(net: str, prefixes: tuple[str, ...]) -> str:
    key = complementary_pin_function_key(net)
    for prefix in prefixes:
        if key.startswith(prefix):
            key = key.removeprefix(prefix)
            break
    return key


def _ethernet_net_label_role(net: str) -> tuple[str, str] | None:
    key = _ethernet_net_label_key(net, _ETHERNET_NET_LABEL_PREFIXES)
    return _ETHERNET_NET_LABEL_ROLES.get(key)


def ethernet_data_label_mismatch_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find assigned Ethernet pins whose explicit net labels name another pair role."""
    pin_nets: dict[str, set[str]] = {}
    net_pins: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
            net_pins.setdefault(net, set()).add(pin)

    roles = {
        pin: role
        for pin, function in observed.pin_functions.items()
        if (role := ethernet_data_pair_function_role(function)) is not None
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for pin in sorted(roles):
        reference, separator, _number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp_references:
            continue
        assigned_nets = pin_nets.get(pin, set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_role = _ethernet_net_label_role(net)
        pin_role = roles[pin]
        if net_role is None or net_role == pin_role:
            continue

        # Same-component pair shorts are owned by complementary_pair_assignment.
        if any(
            other_pin != pin
            and other_pin.rpartition(".")[0] == reference
            and other_role[0] == pin_role[0]
            and other_role[1] != pin_role[1]
            for other_pin in net_pins.get(net, ())
            if (other_role := roles.get(other_pin)) is not None
        ):
            continue

        function = observed.pin_functions[pin]
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"Native Ethernet pin function is {pin_role[0]} {pin_role[1]}, but the "
                    f"assigned net label identifies {net_role[0]} {net_role[1]}. Review the "
                    "pair labels and endpoint pin map; names alone do not establish intent "
                    "or physical connectivity."
                ),
                evidence={
                    "pin": (pin,),
                    "pin_function": (function,),
                    "pin_direction": (pin_role[0],),
                    "pin_side": (pin_role[1],),
                    "net": (net,),
                    "net_direction": (net_role[0],),
                    "net_side": (net_role[1],),
                },
            )
        )
    return tuple(findings)


def _ethernet_management_net_label_role(net: str) -> str | None:
    key = _ethernet_net_label_key(net, _ETHERNET_MANAGEMENT_NET_LABEL_PREFIXES)
    return {"mdc": "clock", "mdio": "data"}.get(key)


def ethernet_management_label_mismatch_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review exact Ethernet MDC/MDIO pin functions against explicit net labels."""
    pin_nets: dict[str, set[str]] = {}
    net_pins: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
            net_pins.setdefault(net.casefold(), set()).add(pin)

    roles = {
        pin.casefold(): (pin, function, role)
        for pin, function in observed.pin_functions.items()
        if (role := ethernet_management_function_role(function)) is not None
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for folded_pin in sorted(roles):
        pin, function, pin_role = roles[folded_pin]
        reference, separator, _number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp_references:
            continue
        assigned_nets = pin_nets.get(folded_pin, set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_role = _ethernet_management_net_label_role(net)
        if net_role is None or net_role == pin_role:
            continue

        # This label-only rule skips a same-component MDC/MDIO short.
        if any(
            other_pin.casefold() != folded_pin
            and other_pin.rpartition(".")[0].casefold() == reference.casefold()
            and other_role[2] != pin_role
            for other_pin in net_pins.get(net.casefold(), ())
            if (other_role := roles.get(other_pin.casefold())) is not None
        ):
            continue

        role_name = "management clock" if pin_role == "clock" else "management data"
        label_name = "management clock" if net_role == "clock" else "management data"
        findings.append(
            Candidate(
                rule_id=MANAGEMENT_RULE_ID,
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"Native Ethernet pin function identifies the {role_name}, but the assigned "
                    f"net label identifies the {label_name}. Review the MDC/MDIO pin map; "
                    "names alone do not establish intent or physical connectivity."
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
