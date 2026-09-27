"""Review hints for repeated connector pin functions in a native netlist."""

from __future__ import annotations

import re

from .models import NetlistContract, SimilarConnectorPinGroup

_CONNECTOR_REFERENCE = re.compile(r"^(?:J|P|X|CN)[0-9]+$", re.IGNORECASE)


def similar_connector_pin_groups(
    observed: NetlistContract,
) -> tuple[SimilarConnectorPinGroup, ...]:
    """Find repeated connector functions on differing or missing nets, without judging intent."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    grouped: dict[tuple[str, str], list[tuple[str, str, str, tuple[str, ...]]]] = {}
    for pin, function in observed.pin_functions.items():
        ref = pin.rsplit(".", 1)[0]
        if _CONNECTOR_REFERENCE.fullmatch(ref) is None:
            continue
        symbol = observed.component_symbols.get(ref)
        if symbol is None:
            continue
        key = (symbol.casefold(), function.casefold())
        grouped.setdefault(key, []).append(
            (pin, symbol, function, tuple(sorted(pin_nets.get(pin, ()))))
        )
    result: list[SimilarConnectorPinGroup] = []
    for _, entries in sorted(grouped.items()):
        if len({pin.rsplit(".", 1)[0] for pin, _, _, _ in entries}) < 2:
            continue
        if len({nets for _, _, _, nets in entries}) == 1 and entries[0][3]:
            continue
        entries.sort()
        result.append(
            SimilarConnectorPinGroup(
                symbol=entries[0][1],
                function=entries[0][2],
                pins={pin: nets for pin, _, _, nets in entries},
            )
        )
    return tuple(result)
