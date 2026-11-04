"""Source-bound connectivity checks for native current-sink LED fixtures."""

from __future__ import annotations

from .hwrepo.netlist_contract_models import NetlistContract


def require_current_sink_led_topology(observed: NetlistContract, *, channels: int) -> None:
    """Require separate native rail-to-anode and output-to-cathode paths."""
    if channels not in {1, 2}:
        raise ValueError("Native current-sink LED fixtures support one or two channels")

    net_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            net_by_pin.setdefault(pin.casefold(), set()).add(net)

    expected_pairs = [("U2.1", "D1.1"), ("U1.1", "D1.2")]
    required_pins = {pin for pair in expected_pairs for pin in pair}
    if channels == 2:
        expected_pairs.extend((("U2.1", "D2.1"), ("U1.2", "D2.2")))
        required_pins.update(pin for pair in expected_pairs for pin in pair)

    if any(len(net_by_pin.get(pin.casefold(), set())) != 1 for pin in required_pins):
        raise ValueError("Native current-sink LED fixture has an unassigned or ambiguous pin")
    if any(
        net_by_pin[first.casefold()] != net_by_pin[second.casefold()]
        for first, second in expected_pairs
    ):
        raise ValueError("Native current-sink LED fixture does not match its source-to-LED paths")

    path_pins = ("U2.1", "U1.1") if channels == 1 else ("U2.1", "U1.1", "U1.2")
    path_nets = tuple(next(iter(net_by_pin[pin.casefold()])) for pin in path_pins)
    if len(path_nets) != len(set(path_nets)):
        raise ValueError("Native current-sink LED fixture shorts distinct rail/output paths")
