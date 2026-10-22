"""Shared exact-net anchor recognition for connector peer heuristics."""

from __future__ import annotations

from collections.abc import Mapping


def connector_footprint_peer_common_anchor_pin_numbers(
    pin_numbers: tuple[str, ...],
    target_pin_number: str,
    references: tuple[str, ...],
    displayed_numbers: Mapping[str, Mapping[str, str]],
    pin_nets: Mapping[str, set[str]],
) -> tuple[str, ...]:
    """Return non-target pins assigned to one exact common net across all peers."""
    anchors: list[str] = []
    for pin_number in pin_numbers:
        if pin_number.casefold() == target_pin_number.casefold():
            continue
        assignments = tuple(
            tuple(
                sorted(
                    pin_nets.get(
                        f"{reference}.{displayed_numbers[reference.casefold()][pin_number.casefold()]}".casefold(),
                        (),
                    ),
                    key=lambda item: (item.casefold(), item),
                )
            )
            for reference in references
        )
        if (
            assignments
            and all(len(nets) == 1 for nets in assignments)
            and len({nets[0] for nets in assignments}) == 1
        ):
            anchors.append(pin_number)
    return tuple(sorted(anchors, key=lambda item: (item.casefold(), item)))
