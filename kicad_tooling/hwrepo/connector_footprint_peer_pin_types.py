"""Typed records for source-bound connector footprint-alias peer scans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .connector_comparison_scope_types import ConnectorComparisonScope, ConnectorComparisonScopes
from .netlist_contract_models import NetlistContract

SIGNAL_ELECTRICAL_TYPES = frozenset(
    {"input", "output", "bidirectional", "tri_state", "open_collector", "open_emitter"}
)


def _freeze_assignments(
    assignments: Mapping[str, tuple[str, ...]],
) -> Mapping[str, tuple[str, ...]]:
    """Copy a peer assignment snapshot so frozen records stay immutable."""
    return MappingProxyType({pin: tuple(nets) for pin, nets in assignments.items()})


def _freeze_peer_assignment_groups(
    groups: ConnectorComparisonScopes | None,
) -> ConnectorComparisonScopes | None:
    if groups is None:
        return None
    return MappingProxyType(
        {
            reference: ConnectorComparisonScope(value.group, value.basis)
            for reference, value in groups.items()
        }
    )


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinScanSource:
    """Exact native source and authored scope used by one footprint-peer scan."""

    observed: NetlistContract
    declared_references: tuple[str, ...]
    peer_assignment_groups: ConnectorComparisonScopes | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "declared_references", tuple(self.declared_references))
        object.__setattr__(
            self,
            "peer_assignment_groups",
            _freeze_peer_assignment_groups(self.peer_assignment_groups),
        )


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinDivergence:
    """A generic pin assignment difference inside a bounded alias candidate group."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    assignments: Mapping[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", _freeze_assignments(self.assignments))


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinNamedDivergence:
    """A named pin assignment difference, including unanchored coverage evidence."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    pin_electrical_type: str
    assignments: Mapping[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    source: ConnectorFootprintPeerPinScanSource
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", _freeze_assignments(self.assignments))


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinOpenOutlier:
    """An eligible generic or named contact open on some peers."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    pin_electrical_type: str
    assignments: Mapping[str, tuple[str, ...]]
    open_pins: tuple[str, ...]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", _freeze_assignments(self.assignments))


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinAllOpen:
    """A generic contact left unassigned on every footprint-alias peer."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    assignments: Mapping[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", _freeze_assignments(self.assignments))


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinNamedAllOpen:
    """A named contact with a supported role left open on every alias peer."""

    footprint: str
    value: str
    pin_number: str
    pin_function: str
    pin_electrical_type: str
    assignments: Mapping[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", _freeze_assignments(self.assignments))


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinScan:
    """Coverage and review candidates derived from one native netlist snapshot."""

    source: ConnectorFootprintPeerPinScanSource
    candidate_group_count: int
    incomplete_pin_inventory_group_count: int
    incomplete_pin_metadata_group_count: int
    differing_pin_metadata_group_count: int
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
    unanchored_all_open_finding_count: int
    all_open_finding_count: int
    divergences: tuple[ConnectorFootprintPeerPinDivergence, ...]
    unanchored_divergences: tuple[ConnectorFootprintPeerPinDivergence, ...]
    named_divergences: tuple[ConnectorFootprintPeerPinNamedDivergence, ...]
    open_outliers: tuple[ConnectorFootprintPeerPinOpenOutlier, ...]
    all_open: tuple[ConnectorFootprintPeerPinAllOpen, ...]
    named_all_open: tuple[ConnectorFootprintPeerPinNamedAllOpen, ...]
    unanchored_open_outliers: tuple[ConnectorFootprintPeerPinOpenOutlier, ...] = ()
