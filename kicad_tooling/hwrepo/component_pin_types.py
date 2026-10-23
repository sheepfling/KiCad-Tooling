"""Shared interpretation of KiCad pin electrical types for component checks."""

from __future__ import annotations

from .models import NetlistContract

_OUTPUT_CAPABLE_PIN_TYPES = frozenset(
    {
        "output",
        "power_out",
        "bidirectional",
        "tri_state",
        "open_collector",
        "open_emitter",
    }
)


def is_output_capable_pin_type(pin_type: str) -> bool:
    """Return whether a native KiCad pin type can drive a connected component."""
    return pin_type.strip().casefold() in _OUTPUT_CAPABLE_PIN_TYPES


def fitted_output_pins_on_net(
    observed: NetlistContract,
    net: str,
    *,
    excluded_references: tuple[str, ...] = (),
) -> tuple[tuple[str, str], ...]:
    """Return fitted, unambiguous output-capable component pins on one exact net."""
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    excluded = {reference.casefold() for reference in excluded_references}
    nets_by_pin: dict[str, list[str]] = {}
    for assigned_net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), []).append(assigned_net)
    types = {
        pin.casefold(): kind.strip().casefold()
        for pin, kind in observed.pin_electrical_types.items()
    }

    peers = []
    for pin in observed.nets.get(net, ()):
        reference = pin.rsplit(".", 1)[0]
        reference_key = reference.casefold()
        pin_type = types.get(pin.casefold(), "")
        if (
            reference_key not in fitted
            or reference_key in dnp
            or reference_key in excluded
            or nets_by_pin.get(pin.casefold()) != [net]
            or not is_output_capable_pin_type(pin_type)
        ):
            continue
        peers.append((pin, pin_type))
    return tuple(sorted(peers, key=lambda item: (item[0].casefold(), item[0])))
