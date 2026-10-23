"""Review CAN controller TX/RX functions against explicit CAN net labels."""

from __future__ import annotations

from .can_signal_functions import can_signal_role_and_channel
from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "bus.can_tx_rx_label_mismatch"


def can_tx_rx_label_mismatch_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find explicit CAN/FDCAN TX/RX pins assigned to opposite-role net labels.

    This opt-in review cue requires a fitted U/IC, complete native pin inventory,
    and one exact native net assignment. Generic TX/RX names and connector pins
    are intentionally outside the predicate.
    """
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    function_entries: dict[str, list[tuple[str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        function_entries.setdefault(pin.casefold(), []).append((pin, function))

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for folded_pin, entries in sorted(function_entries.items()):
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

        pin_role = can_signal_role_and_channel(function)
        if pin_role is None:
            continue
        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if inventory is None or number.casefold() not in {item.casefold() for item in inventory}:
            continue

        assigned_nets = nets_by_pin.get(folded_pin, set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_role = can_signal_role_and_channel(net)
        if net_role is None or pin_role[0] == net_role[0]:
            continue

        pin_direction = pin_role[0].upper()
        net_direction = net_role[0].upper()
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"Explicit CAN/FDCAN pin function indicates {pin_direction}, but the net "
                    f"name {net!r} indicates {net_direction}. Review the endpoint pin map and "
                    "naming convention; labels alone do not establish required direction "
                    "or topology."
                ),
                evidence={
                    "pin": (pin,),
                    "pin_function": (function,),
                    "pin_role": (pin_role[0],),
                    "pin_channel": (pin_role[1],),
                    "net": (net,),
                    "net_role": (net_role[0],),
                    "net_channel": (net_role[1],),
                },
            )
        )
    return tuple(findings)
