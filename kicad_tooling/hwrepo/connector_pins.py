"""Review-hint facade for connector and component pin analyses."""

from __future__ import annotations

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
    component_peer_pin_assignment_scans,
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
from .connector_identity import (
    connector_candidate_references,
    power_function_key,
    similar_connector_pin_groups,
)
from .connector_peer_pin_coverage import (
    connector_peer_pin_heuristic_coverage,
)
from .connector_peer_pin_findings import (
    connector_peer_pin_assignment_divergences,
    connector_peer_pin_assignment_outliers,
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
