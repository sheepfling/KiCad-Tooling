"""Review-hint facade for connector and component pin analyses."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TypeAlias

from .component_peer_pin_evaluation import component_peer_pin_assignment_scans
from .component_peer_pin_findings import (
    component_peer_bidirectional_pin_outliers,
    component_peer_power_output_pin_outliers,
    component_peer_power_pin_assignment_divergences,
    component_peer_signal_input_pin_outliers,
    component_peer_signal_output_pin_outliers,
)
from .component_peer_pin_scan import (
    ComponentPeerPinAssignmentScans,
    PeerPinAssignmentOutlier,
    PeerPinAssignmentScan,
    PeerPowerPinAssignmentDivergence,
)
from .component_pin_patterns import (
    RepeatedComponentSupplyPins,
    UnconnectedGenericPowerInputComponentPin,
    UnconnectedNamedComponentPin,
    component_supply_pins_on_different_nets,
    unconnected_generic_power_input_component_pins,
    unconnected_named_component_pins,
)
from .component_return_pins import unconnected_component_return_pins
from .connector_comparison_scope_types import (
    ConnectorComparisonScope,
    ConnectorComparisonScopes,
)
from .connector_coverage_models import ConnectorMappedPinEvidence
from .connector_identity import (
    connector_candidate_references,
    power_function_key,
)
from .connector_identity import (
    similar_connector_pin_groups as _similar_connector_pin_groups,
)
from .connector_peer_pin_candidate_results import ConnectorPeerPinFindingCounts
from .connector_peer_pin_coverage import (
    connector_peer_pin_heuristic_coverage as _connector_peer_pin_heuristic_coverage,
)
from .connector_peer_pin_findings import (
    connector_peer_pin_assignment_divergences as _connector_peer_pin_assignment_divergences,
)
from .connector_peer_pin_findings import (
    connector_peer_pin_assignment_outliers as _connector_peer_pin_assignment_outliers,
)
from .connector_peer_pin_models import (
    ConnectorPeerPinHeuristicCoverage,
    SimilarConnectorPinGroup,
)
from .connector_peer_pin_scan import (
    ConnectorPeerPinAssignmentDivergence,
    ConnectorPeerPinAssignmentOutlier,
)
from .connector_return_pins import (
    ConnectorReturnCoverage,
    UnconnectedGenericPowerInputConnectorPin,
    UnconnectedNamedConnectorPin,
    connectors_without_connected_return,
    unconnected_generic_power_input_connector_pins,
    unconnected_named_connector_pins,
)
from .netlist_contract_models import NetlistContract

ConnectorComparisonScopeInputValue: TypeAlias = ConnectorComparisonScope | tuple[str, str]
ConnectorComparisonScopeInput: TypeAlias = Mapping[str, ConnectorComparisonScopeInputValue]


def _typed_comparison_scopes(
    scopes: ConnectorComparisonScopeInput | ConnectorComparisonScopes | None,
) -> ConnectorComparisonScopes | None:
    """Adapt the former tuple-valued scope map at the public compatibility facade."""
    if scopes is None:
        return None
    normalized: dict[str, ConnectorComparisonScope] = {}
    for reference, value in scopes.items():
        if isinstance(value, ConnectorComparisonScope):
            normalized[reference] = value
        else:
            group, basis = value
            normalized[reference] = ConnectorComparisonScope(group=group, basis=basis)
    return MappingProxyType(normalized)


def similar_connector_pin_groups(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
    peer_assignment_groups: ConnectorComparisonScopeInput | ConnectorComparisonScopes | None = None,
    return_comparison_groups: ConnectorComparisonScopeInput
    | ConnectorComparisonScopes
    | None = None,
    supply_comparison_groups: ConnectorComparisonScopeInput
    | ConnectorComparisonScopes
    | None = None,
    *,
    include_consistent: bool = False,
) -> tuple[SimilarConnectorPinGroup, ...]:
    """Compatibility facade for shared connector role and scope comparisons."""
    return _similar_connector_pin_groups(
        observed,
        declared_references,
        reviewed_connector_pins,
        _typed_comparison_scopes(peer_assignment_groups),
        _typed_comparison_scopes(return_comparison_groups),
        _typed_comparison_scopes(supply_comparison_groups),
        include_consistent=include_consistent,
    )


def connector_peer_pin_assignment_divergences(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: ConnectorComparisonScopeInput | ConnectorComparisonScopes | None = None,
) -> tuple[ConnectorPeerPinAssignmentDivergence, ...]:
    """Preserve tuple-valued scope input for existing connector facade callers."""
    return _connector_peer_pin_assignment_divergences(
        observed,
        declared_references,
        _typed_comparison_scopes(peer_assignment_groups),
    )


def connector_peer_pin_assignment_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: ConnectorComparisonScopeInput | ConnectorComparisonScopes | None = None,
) -> tuple[ConnectorPeerPinAssignmentOutlier, ...]:
    """Preserve tuple-valued scope input for existing connector facade callers."""
    return _connector_peer_pin_assignment_outliers(
        observed,
        declared_references,
        _typed_comparison_scopes(peer_assignment_groups),
    )


def connector_peer_pin_heuristic_coverage(
    observed: NetlistContract,
    netlist_sha256: str,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
    peer_assignment_groups: ConnectorComparisonScopeInput | ConnectorComparisonScopes | None = None,
    *,
    finding_counts: ConnectorPeerPinFindingCounts,
) -> ConnectorPeerPinHeuristicCoverage:
    """Adapt legacy public scope maps before entering the typed coverage owner."""
    return _connector_peer_pin_heuristic_coverage(
        observed,
        netlist_sha256,
        declared_references,
        reviewed_connector_pins,
        _typed_comparison_scopes(peer_assignment_groups),
        finding_counts=finding_counts,
    )


__all__ = (
    "ComponentPeerPinAssignmentScans",
    "ConnectorPeerPinAssignmentDivergence",
    "ConnectorPeerPinAssignmentOutlier",
    "ConnectorReturnCoverage",
    "PeerPinAssignmentOutlier",
    "PeerPinAssignmentScan",
    "PeerPowerPinAssignmentDivergence",
    "RepeatedComponentSupplyPins",
    "UnconnectedGenericPowerInputComponentPin",
    "UnconnectedGenericPowerInputConnectorPin",
    "UnconnectedNamedComponentPin",
    "UnconnectedNamedConnectorPin",
    "component_peer_bidirectional_pin_outliers",
    "component_peer_pin_assignment_scans",
    "component_peer_power_output_pin_outliers",
    "component_peer_power_pin_assignment_divergences",
    "component_peer_signal_input_pin_outliers",
    "component_peer_signal_output_pin_outliers",
    "component_supply_pins_on_different_nets",
    "connector_candidate_references",
    "connector_peer_pin_assignment_divergences",
    "connector_peer_pin_assignment_outliers",
    "connector_peer_pin_heuristic_coverage",
    "connectors_without_connected_return",
    "power_function_key",
    "similar_connector_pin_groups",
    "unconnected_component_return_pins",
    "unconnected_generic_power_input_component_pins",
    "unconnected_generic_power_input_connector_pins",
    "unconnected_named_component_pins",
    "unconnected_named_connector_pins",
)
