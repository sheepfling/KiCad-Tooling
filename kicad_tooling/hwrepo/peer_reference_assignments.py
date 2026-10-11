"""Shared interpretation of explicit passive and power-input return pins."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import NetlistContract
from .return_nets import is_return_like_net_name

_NON_SIGNAL_REFERENCE = re.compile(
    r"(?:^|[^A-Z0-9])(?:CHASSIS|SHIELD|FRAME|PE)(?:$|[^A-Z0-9])",
    re.IGNORECASE,
)
_REFERENCE_PIN_TYPES = frozenset({"passive", "power_in"})


@dataclass(frozen=True)
class PeerReferencePinAssignment:
    """One assigned return-like pin from a complete native inventory."""

    pin: str
    function: str
    electrical_type: str
    net: str


@dataclass(frozen=True)
class PeerReferenceAssignments:
    """Return-pin assignments and their single-domain result when available."""

    net: str | None
    pins: tuple[PeerReferencePinAssignment, ...]


def peer_reference_assignments(
    reference: str,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    pin_numbers: tuple[str, ...],
) -> PeerReferenceAssignments:
    """Resolve explicit return pins from complete native pin metadata.

    A split assignment is preserved in ``pins`` while ``net`` remains unknown.
    Missing inventory metadata, ambiguous assignments, named shield/chassis
    pins, and non-passive/non-power-input return pins cannot establish a
    reference domain.
    """
    if not pin_numbers:
        return PeerReferenceAssignments(net=None, pins=())
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    assignments: list[PeerReferencePinAssignment] = []
    for number in pin_numbers:
        pin = f"{reference}.{number}"
        pin_key = pin.casefold()
        function = functions.get(pin_key)
        electrical_type = electrical_types.get(pin_key)
        if function is None or electrical_type is None:
            return PeerReferenceAssignments(net=None, pins=())
        if _NON_SIGNAL_REFERENCE.search(function) or not is_return_like_net_name(function):
            continue
        if electrical_type not in _REFERENCE_PIN_TYPES:
            return PeerReferenceAssignments(net=None, pins=())
        nets = pin_nets.get(pin_key, set())
        if len(nets) != 1:
            return PeerReferenceAssignments(net=None, pins=())
        assignments.append(
            PeerReferencePinAssignment(
                pin=pin,
                function=function,
                electrical_type=electrical_type,
                net=next(iter(nets)),
            )
        )
    if not assignments:
        return PeerReferenceAssignments(net=None, pins=())
    ordered = tuple(sorted(assignments, key=lambda item: item.pin.casefold()))
    reference_nets = {item.net.casefold() for item in ordered}
    reference_net = ordered[0].net if len(reference_nets) == 1 else None
    return PeerReferenceAssignments(net=reference_net, pins=ordered)
