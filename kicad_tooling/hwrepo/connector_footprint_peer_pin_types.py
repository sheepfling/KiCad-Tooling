"""Typed records for source-bound connector footprint-alias peer scans."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorFootprintPeerPinDivergence:
    """A generic pin assignment difference inside a bounded alias candidate group."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    assignments: dict[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorFootprintPeerPinNamedDivergence:
    """A named pin assignment difference, including unanchored coverage evidence."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    pin_electrical_type: str
    assignments: dict[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorFootprintPeerPinOpenOutlier:
    """An eligible generic or named contact open on some peers."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    pin_electrical_type: str
    assignments: dict[str, tuple[str, ...]]
    open_pins: tuple[str, ...]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorFootprintPeerPinAllOpen:
    """A generic contact left unassigned on every footprint-alias peer."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    assignments: dict[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorFootprintPeerPinNamedAllOpen:
    """A named power contact left open on every footprint-alias peer."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    pin_electrical_type: str
    assignments: dict[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorFootprintPeerPinScan:
    """Coverage and review candidates derived from one native netlist snapshot."""

    candidate_group_count: int
    incomplete_pin_inventory_group_count: int
    incomplete_pin_metadata_group_count: int
    eligible_peer_group_count: int
    peer_scope_group_count: int
    evaluated_pin_group_count: int
    compared_pin_group_count: int
    common_assignment_pin_group_count: int
    different_assignment_pin_group_count: int
    unassigned_assignment_pin_group_count: int
    ambiguous_assignment_pin_group_count: int
    generic_different_assignment_pin_group_count: int
    non_generic_different_assignment_pin_group_count: int
    common_anchor_group_count: int
    unanchored_different_assignment_pin_group_count: int
    finding_count: int
    open_peer_pin_group_count: int
    unanchored_open_peer_pin_group_count: int
    open_outlier_finding_count: int
    all_open_peer_pin_group_count: int
    unanchored_all_open_peer_pin_group_count: int
    all_open_finding_count: int
    divergences: tuple[ConnectorFootprintPeerPinDivergence, ...]
    named_divergences: tuple[ConnectorFootprintPeerPinNamedDivergence, ...]
    open_outliers: tuple[ConnectorFootprintPeerPinOpenOutlier, ...]
    all_open: tuple[ConnectorFootprintPeerPinAllOpen, ...]
    named_all_open: tuple[ConnectorFootprintPeerPinNamedAllOpen, ...]
