"""Can peer heuristics for deterministic KiCad bus analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bus_signal_roles import can_function_role
from .models import NetlistContract


@dataclass(frozen=True)
class CanPeerAssignmentDivergence:
    """Complete CAN pin pairs that share one side but disagree on the other."""

    shared_role: Literal["CANH", "CANL"]
    shared_net: str
    complementary_role: Literal["CANH", "CANL"]
    complementary_nets: tuple[str, ...]
    participants: tuple[str, ...]


def can_peer_assignment_divergences(
    observed: NetlistContract,
) -> tuple[CanPeerAssignmentDivergence, ...]:
    """Review complete CAN pin pairs that share only one exact native net.

    Pin-function names and native assignments identify candidates; they do not
    establish that the components belong to one bus or that all peers must
    share both nets. DNP, incomplete, multi-pin-per-role, and same-net pairs
    are left to other rules or skipped as ambiguous.
    """
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    symbols_by_reference = {
        reference.casefold(): reference for reference in observed.component_symbols
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    role_pins: dict[str, dict[str, list[str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, _pin_number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp:
            continue
        if reference.casefold() not in symbols_by_reference:
            continue
        role = can_function_role(function)
        if role is not None:
            role_pins.setdefault(reference.casefold(), {}).setdefault(role, []).append(pin)

    participants: list[tuple[str, str, str, str, str]] = []
    for reference_key, roles in sorted(role_pins.items()):
        if len(roles.get("CANH", ())) != 1 or len(roles.get("CANL", ())) != 1:
            continue
        high_pin = roles["CANH"][0]
        low_pin = roles["CANL"][0]
        high_nets = nets_by_pin.get(high_pin.casefold(), set())
        low_nets = nets_by_pin.get(low_pin.casefold(), set())
        if len(high_nets) != 1 or len(low_nets) != 1:
            continue
        high_net = next(iter(high_nets))
        low_net = next(iter(low_nets))
        if high_net == low_net:
            continue
        participants.append(
            (
                symbols_by_reference[reference_key],
                high_pin,
                high_net,
                low_pin,
                low_net,
            )
        )

    groups: dict[tuple[str, str], list[tuple[str, str, str, str, str]]] = {}
    for participant in participants:
        _reference, high_pin, high_net, low_pin, low_net = participant
        groups.setdefault(("CANH", high_net), []).append(participant)
        groups.setdefault(("CANL", low_net), []).append(participant)

    divergences: list[CanPeerAssignmentDivergence] = []
    for (shared_role, shared_net), peers in sorted(groups.items()):
        if len(peers) < 2:
            continue
        complementary_role: Literal["CANH", "CANL"] = "CANL" if shared_role == "CANH" else "CANH"
        complementary_nets = tuple(
            sorted({peer[4] if complementary_role == "CANL" else peer[2] for peer in peers})
        )
        if len(complementary_nets) < 2:
            continue
        participant_evidence = tuple(
            sorted(
                f"{reference}:{high_pin}=CANH/{high_net};{low_pin}=CANL/{low_net}"
                for reference, high_pin, high_net, low_pin, low_net in peers
            )
        )
        divergences.append(
            CanPeerAssignmentDivergence(
                shared_role=shared_role,  # type: ignore[arg-type]
                shared_net=shared_net,
                complementary_role=complementary_role,
                complementary_nets=complementary_nets,
                participants=participant_evidence,
            )
        )
    return tuple(divergences)
