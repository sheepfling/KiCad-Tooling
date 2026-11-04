"""Named source records for the bounded transformer-winding scan."""

from __future__ import annotations

from dataclasses import dataclass

from .netlist_contract_models import NetlistContract


@dataclass(frozen=True, slots=True)
class TransformerWindingPinGroup:
    """One reviewed winding and the exact terminal numbers assigned to it."""

    name: str
    pin_numbers: tuple[str, str]


@dataclass(frozen=True, slots=True)
class TransformerPinNetAssignment:
    """One transformer terminal and its uniquely assigned native net."""

    pin_number: str
    net: str


@dataclass(frozen=True, slots=True)
class SupportedTransformerObservation:
    """A supported transformer recognized from one exact normalized netlist."""

    observed: NetlistContract
    reference: str
    symbol: str
    value: str
    winding_groups: tuple[TransformerWindingPinGroup, ...]
    pin_assignments: tuple[TransformerPinNetAssignment, ...]
