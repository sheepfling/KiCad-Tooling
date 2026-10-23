"""Review multiple fitted serial transmit functions assigned to one schematic net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .return_nets import is_return_like_net_name
from .serial_participants import is_serial_ic_reference, serial_function_role_and_channel

RULE_ID = "bus.serial_tx_outputs_share_net"
_SUPPORTED_PIN_TYPES = frozenset({"output", "tri_state", "bidirectional", "passive"})


def serial_tx_output_sharing_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find unambiguous TX-function groups not already typed as output conflicts.

    A net with two or more native ``output`` pins is left to ERC. This review
    prompt focuses on same-role serial pins whose native electrical types do
    not already identify an output-to-output conflict.
    """
    fitted = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    by_net: dict[str, list[tuple[str, str, str, str, str]]] = {}
    display_names: dict[str, set[str]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, _pin_number = pin.rpartition(".")
        reference_key = reference.casefold()
        canonical_reference = fitted.get(reference_key)
        if (
            not separator
            or canonical_reference is None
            or reference_key in dnp
            or not is_serial_ic_reference(canonical_reference)
        ):
            continue
        role_channel = serial_function_role_and_channel(function)
        if role_channel is None or role_channel[0] != "tx":
            continue
        assignments = nets_by_pin.get(pin.casefold(), set())
        electrical_type = pin_types.get(pin.casefold())
        if len(assignments) != 1 or electrical_type not in _SUPPORTED_PIN_TYPES:
            continue
        net = next(iter(assignments))
        if is_return_like_net_name(net):
            continue
        key = net.casefold()
        by_net.setdefault(key, []).append(
            (canonical_reference, pin, function, electrical_type, role_channel[1])
        )
        display_names.setdefault(key, set()).add(net)

    findings: list[Candidate] = []
    for key, endpoints in sorted(by_net.items()):
        ordered = sorted(set(endpoints), key=lambda item: tuple(part.casefold() for part in item))
        if len(display_names[key]) != 1:
            continue
        by_reference: dict[str, list[tuple[str, str, str, str, str]]] = {}
        for endpoint in ordered:
            by_reference.setdefault(endpoint[0].casefold(), []).append(endpoint)
        if len(by_reference) < 2 or any(len(items) != 1 for items in by_reference.values()):
            continue
        if sum(item[3] == "output" for item in ordered) >= 2:
            continue

        net = next(iter(display_names[key]))
        participants = tuple(
            sorted((items[0][0] for items in by_reference.values()), key=str.casefold)
        )
        pins = tuple(sorted((item[1] for item in ordered), key=str.casefold))
        functions = tuple(sorted((item[2] for item in ordered), key=str.casefold))
        channels = tuple(sorted((item[4].upper() for item in ordered), key=str.casefold))
        electrical_types = tuple(sorted((item[3] for item in ordered), key=str.casefold))
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{', '.join(participants)}: serial TX functions share {net}",
                message=(
                    f"Fitted IC transmit-function pins {', '.join(pins)} share one schematic net "
                    f"({net}), while their native electrical pin types are "
                    f"{', '.join(electrical_types)}. Review whether multiple transmitters are "
                    "intentionally sharing this net or whether one pin assignment is wrong. "
                    "The function names do not prove driver behavior or required peer topology."
                ),
                evidence={
                    "components": participants,
                    "channels": channels,
                    "functions": functions,
                    "pins": pins,
                    "pin_types": electrical_types,
                    "net": (net,),
                },
            )
        )
    return tuple(findings)
