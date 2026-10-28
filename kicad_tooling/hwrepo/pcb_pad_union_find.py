"""Case-insensitive connected groups for native PCB pad observations."""

from __future__ import annotations

from .pcb_connectivity_observations import PcbPadConnectivityObservation


class PcbPadUnionFind:
    """Group pads using the native pad-to-pad copper connectivity evidence."""

    def __init__(self, pads: tuple[PcbPadConnectivityObservation, ...]) -> None:
        self._parent = {item.pad.casefold(): item.pad.casefold() for item in pads}
        for item in pads:
            for other in item.connected_pads:
                self.join(item.pad, other)

    def find(self, pad: str) -> str:
        key = pad.casefold()
        if key not in self._parent:
            return ""
        while self._parent[key] != key:
            self._parent[key] = self._parent[self._parent[key]]
            key = self._parent[key]
        return key

    def join(self, first: str, second: str) -> None:
        first_key = first.casefold()
        second_key = second.casefold()
        if first_key not in self._parent or second_key not in self._parent:
            return
        first_root = self.find(first_key)
        second_root = self.find(second_key)
        if first_root != second_root:
            self._parent[max(first_root, second_root)] = min(first_root, second_root)
