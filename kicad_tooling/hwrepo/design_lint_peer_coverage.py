"""Coverage evidence adapters for digital-interface peer heuristics."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Literal

from .component_peer_pin_models import ComponentPeerPinRuleCoverage
from .component_peer_pin_scan import ComponentPeerPinAssignmentScans, PeerPinAssignmentScan
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .digital_peer_voltage_models import DigitalPeerVoltageRuleCoverage
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan
from .models import (
    DesignLintRuleOverride,
    UsbDataPathMap,
)
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_models import (
    SerialPeerReferenceCoverageReport,
    SerialPeerReferenceLinkCoverageEntry,
)
from .serial_peer_reference_types import SerialPeerReferenceScan
from .usb_peer_reference_models import (
    UsbPeerDataLineCoverage,
    UsbPeerDataPathCoverage,
    UsbPeerDataSeriesResistorCoverage,
    UsbPeerDataShuntBranchCoverage,
    UsbPeerEndpointGroupCoverage,
    UsbPeerReferenceCoverageReport,
    UsbPeerReferencePathCoverageEntry,
    UsbPeerReferencePinCoverage,
)
from .usb_peer_reference_types import (
    UsbPeerDataSeriesResistor,
    UsbPeerDataShuntBranch,
    UsbPeerReferencePathCoverage,
    UsbPeerReferenceScan,
)


def digital_peer_voltage_coverage(
    scan: DigitalPeerVoltageScan,
    context: DigitalPeerVoltageLintContext,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
) -> tuple[DigitalPeerVoltageRuleCoverage, ...]:
    """Bind bounded peer-voltage applicability counts to their sources and policy."""
    result: list[DigitalPeerVoltageRuleCoverage] = []
    for item in scan.coverage:
        rule_id: Literal["bus.spi_peer_voltage_review", "bus.serial_peer_voltage_review"] = (
            "bus.spi_peer_voltage_review"
            if item.interface == "SPI"
            else "bus.serial_peer_voltage_review"
        )
        override = overrides.get(rule_id)
        mode = default_modes[rule_id] if override is None else override.mode
        status: Literal["NO_SUPPORTED_ENDPOINTS", "NO_DIRECT_PEERS", "INCOMPLETE", "EVALUATED"] = (
            "NO_SUPPORTED_ENDPOINTS"
            if item.recognized_endpoint_count == 0
            else "INCOMPLETE"
            if item.assigned_endpoint_count < item.recognized_endpoint_count
            or item.voltage_comparison_count < item.direct_peer_link_count
            else "NO_DIRECT_PEERS"
            if item.direct_peer_link_count == 0
            else "EVALUATED"
        )
        result.append(
            DigitalPeerVoltageRuleCoverage(
                rule_id=rule_id,
                status=status,
                mode=mode,
                netlist_sha256=netlist_sha256,
                authored_map_state=context.state,
                authored_map_path=context.source_path,
                authored_map_sha256=context.source_sha256,
                recognized_endpoint_count=item.recognized_endpoint_count,
                assigned_endpoint_count=item.assigned_endpoint_count,
                direct_peer_link_count=item.direct_peer_link_count,
                voltage_comparison_count=item.voltage_comparison_count,
                same_voltage_link_count=item.same_voltage_link_count,
                different_voltage_link_count=item.different_voltage_link_count,
                mapped_mismatch_link_count=item.mapped_mismatch_link_count,
                candidate_group_count=item.review_candidate_group_count,
            )
        )
    return tuple(result)


def component_peer_pin_rule_coverage(
    scans: ComponentPeerPinAssignmentScans,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    candidate_items: Sequence[Candidate],
    netlist_sha256: str,
) -> tuple[ComponentPeerPinRuleCoverage, ...]:
    """Bind component-peer pin applicability and findings to one native netlist."""
    rule_scans: tuple[tuple[DesignLintRuleId, PeerPinAssignmentScan], ...] = (
        ("component.peer_power_output_unconnected", scans.power_output),
        ("component.peer_signal_output_unconnected", scans.signal_output),
        ("component.peer_signal_input_unconnected", scans.signal_input),
        ("component.peer_bidirectional_pin_unconnected", scans.bidirectional),
    )
    result: list[ComponentPeerPinRuleCoverage] = []
    for rule_id, scan in rule_scans:
        peer_group_count = scan.exact_symbol_peer_group_count + scan.part_id_peer_group_count
        if peer_group_count == 0:
            status = (
                "INCOMPLETE_COMPONENT_IDENTITY"
                if scan.part_id_candidate_group_count > 0
                else "NO_COMPARABLE_PEERS"
            )
        elif scan.complete_pin_inventory_group_count == 0:
            status = "INCOMPLETE_PIN_INVENTORY"
        elif scan.matching_electrical_type_pin_group_count == 0:
            status = "NO_MATCHING_PIN_TYPES"
        elif scan.compatible_function_pin_group_count == 0:
            status = "NO_COMPATIBLE_PIN_FUNCTIONS"
        elif scan.unambiguous_assignment_pin_group_count == 0:
            status = "NO_UNAMBIGUOUS_ASSIGNMENTS"
        elif (
            scan.incomplete_pin_inventory_group_count > 0
            or scan.part_id_incomplete_component_identity_group_count > 0
        ):
            status = "PARTIALLY_EVALUATED"
        else:
            status = "EVALUATED"
        override = overrides.get(rule_id)
        finding_count = sum(item.rule_id == rule_id for item in candidate_items)
        candidate_count = len(scan.outliers)
        result.append(
            ComponentPeerPinRuleCoverage(
                rule_id=rule_id,
                status=status,
                mode=default_modes[rule_id] if override is None else override.mode,
                netlist_sha256=netlist_sha256,
                exact_symbol_peer_group_count=scan.exact_symbol_peer_group_count,
                part_id_peer_group_count=scan.part_id_peer_group_count,
                part_id_candidate_group_count=scan.part_id_candidate_group_count,
                part_id_incomplete_component_identity_group_count=(
                    scan.part_id_incomplete_component_identity_group_count
                ),
                part_id_incomplete_component_identity_references=(
                    scan.part_id_incomplete_component_identity_references
                ),
                incomplete_pin_inventory_group_count=scan.incomplete_pin_inventory_group_count,
                incomplete_pin_inventory_references=scan.incomplete_pin_inventory_references,
                complete_pin_inventory_group_count=scan.complete_pin_inventory_group_count,
                comparable_pin_group_count=scan.comparable_pin_group_count,
                matching_electrical_type_pin_group_count=(
                    scan.matching_electrical_type_pin_group_count
                ),
                compatible_function_pin_group_count=scan.compatible_function_pin_group_count,
                ambiguous_assignment_pin_group_count=scan.ambiguous_assignment_pin_group_count,
                unambiguous_assignment_pin_group_count=(
                    scan.unambiguous_assignment_pin_group_count
                ),
                candidate_group_count=candidate_count,
                deduplicated_candidate_group_count=scan.deduplicated_candidate_group_count,
                finding_count=finding_count,
                suppressed_candidate_count=candidate_count - finding_count,
            )
        )
    return tuple(result)


def _usb_peer_reference_path_entry(
    item: UsbPeerReferencePathCoverage,
) -> UsbPeerReferencePathCoverageEntry:
    """Serialize one matched USB peer path as source-bound coverage evidence."""

    def data_line(
        connector_pins: tuple[str, ...],
        phy_pins: tuple[str, ...],
        connector_net: str,
        phy_net: str,
        series_resistor: UsbPeerDataSeriesResistor | None,
        shunt_branches: tuple[UsbPeerDataShuntBranch, ...],
    ) -> UsbPeerDataLineCoverage:
        resistor = (
            None
            if series_resistor is None
            else UsbPeerDataSeriesResistorCoverage(
                reference=series_resistor.reference,
                symbol=series_resistor.symbol,
                footprint=series_resistor.footprint,
                value=series_resistor.value,
                connector_pin=series_resistor.connector_pin,
                phy_pin=series_resistor.phy_pin,
                connector_net=series_resistor.connector_net,
                phy_net=series_resistor.phy_net,
            )
        )
        return UsbPeerDataLineCoverage(
            connector_pins=connector_pins,
            phy_pins=phy_pins,
            connector_net=connector_net,
            phy_net=phy_net,
            series_resistor=resistor,
            shunt_branches=tuple(
                UsbPeerDataShuntBranchCoverage(
                    data_pin=branch.data_pin,
                    reference_pin=branch.reference_pin,
                    symbol=branch.symbol,
                    data_net=branch.data_net,
                    reference_net=branch.reference_net,
                )
                for branch in shunt_branches
            ),
        )

    link = item.data_link
    return UsbPeerReferencePathCoverageEntry(
        connector_reference=item.connector_reference,
        phy_reference=item.phy_reference,
        connector_symbol=item.connector_symbol,
        phy_symbol=item.phy_symbol,
        connector_footprint=item.connector_footprint,
        phy_footprint=item.phy_footprint,
        connector_reference_net=item.connector_reference_net,
        phy_reference_net=item.phy_reference_net,
        connector_reference_pins=tuple(
            UsbPeerReferencePinCoverage(
                pin=pin.pin,
                function=pin.function,
                electrical_type=pin.electrical_type,
                net=pin.net,
            )
            for pin in item.connector_reference_pins
        ),
        phy_reference_pins=tuple(
            UsbPeerReferencePinCoverage(
                pin=pin.pin,
                function=pin.function,
                electrical_type=pin.electrical_type,
                net=pin.net,
            )
            for pin in item.phy_reference_pins
        ),
        reference_disposition=item.reference_disposition,
        data_path=UsbPeerDataPathCoverage(
            positive=data_line(
                link.connector_positive_pins,
                link.phy_positive_pins,
                link.connector_positive_net,
                link.phy_positive_net,
                link.positive_series_resistor,
                link.positive_shunt_branches,
            ),
            negative=data_line(
                link.connector_negative_pins,
                link.phy_negative_pins,
                link.connector_negative_net,
                link.phy_negative_net,
                link.negative_series_resistor,
                link.negative_shunt_branches,
            ),
            port_group=link.port_group,
        ),
    )


def usb_peer_reference_coverage(
    scan: UsbPeerReferenceScan,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
    usb_data_path_map: UsbDataPathMap | None,
) -> UsbPeerReferenceCoverageReport:
    """Bind USB heuristic applicability counts to the native source and policy."""
    rule_id: Literal["bus.usb_peer_reference_review"] = "bus.usb_peer_reference_review"
    mode = default_modes[rule_id]
    if override := overrides.get(rule_id):
        mode = override.mode
    item = scan.coverage
    recognized_group_count = item.recognized_connector_group_count + item.recognized_phy_group_count
    status: Literal["NO_USB_ENDPOINTS", "INCOMPLETE", "NO_SUPPORTED_PEER_PATHS", "EVALUATED"] = (
        "NO_USB_ENDPOINTS"
        if recognized_group_count == 0
        else "INCOMPLETE"
        if item.incomplete_group_count > 0
        else "NO_SUPPORTED_PEER_PATHS"
        if item.supported_data_path_count == 0
        else "EVALUATED"
    )
    map_sha256 = (
        hashlib.sha256(usb_data_path_map.model_dump_json().encode("utf-8")).hexdigest()
        if usb_data_path_map is not None
        else None
    )
    return UsbPeerReferenceCoverageReport(
        rule_id=rule_id,
        status=status,
        mode=mode,
        netlist_sha256=netlist_sha256,
        usb_data_path_map_sha256=map_sha256,
        endpoint_groups=tuple(
            UsbPeerEndpointGroupCoverage(
                endpoint_role=entry.endpoint_role,
                reference=entry.reference,
                port_group=entry.port_group,
                disposition=entry.disposition,
            )
            for entry in item.endpoint_groups
        ),
        path_entries=tuple(_usb_peer_reference_path_entry(entry) for entry in item.path_entries),
        recognized_connector_group_count=item.recognized_connector_group_count,
        supported_connector_group_count=item.supported_connector_group_count,
        recognized_phy_group_count=item.recognized_phy_group_count,
        supported_phy_group_count=item.supported_phy_group_count,
        dnp_group_count=item.dnp_group_count,
        incomplete_group_count=item.incomplete_group_count,
        supported_data_path_count=item.supported_data_path_count,
        common_reference_path_count=item.common_reference_path_count,
        separate_reference_path_count=item.separate_reference_path_count,
        mapped_separate_reference_path_count=item.mapped_separate_reference_path_count,
        candidate_group_count=item.review_candidate_group_count,
    )


def serial_peer_reference_coverage(
    scan: SerialPeerReferenceScan,
    context: SerialPeerRosterContext,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
) -> SerialPeerReferenceCoverageReport:
    """Bind serial reference applicability counts to the native source and policy."""
    rule_id: Literal["bus.serial_peer_reference_review"] = "bus.serial_peer_reference_review"
    mode = default_modes[rule_id]
    if override := overrides.get(rule_id):
        mode = override.mode
    discovered = scan.native_peer_link_count + scan.label_peer_link_count
    status: Literal["NO_DIRECT_PEERS", "INCOMPLETE", "EVALUATED"] = (
        "NO_DIRECT_PEERS"
        if discovered == 0
        else "INCOMPLETE"
        if scan.incomplete_reference_link_count > 0
        else "EVALUATED"
    )
    map_sha256 = (
        hashlib.sha256(context.analysis.model_dump_json().encode("utf-8")).hexdigest()
        if context.analysis is not None
        else None
    )
    return SerialPeerReferenceCoverageReport(
        rule_id=rule_id,
        status=status,
        mode=mode,
        netlist_sha256=netlist_sha256,
        authored_map_state=context.state,
        authored_map_path=context.source_path,
        authored_map_source_sha256=context.source_sha256,
        authored_serial_peer_map_sha256=map_sha256,
        link_entries=tuple(
            SerialPeerReferenceLinkCoverageEntry(
                discovery_basis=entry.discovery_basis,
                first_reference=entry.first_reference,
                second_reference=entry.second_reference,
                signal_group=entry.signal_group,
                signal_nets=entry.signal_nets,
                signal_pins=entry.signal_pins,
                disposition=entry.disposition,
            )
            for entry in scan.link_entries
        ),
        native_peer_link_count=scan.native_peer_link_count,
        label_peer_link_count=scan.label_peer_link_count,
        supported_reference_link_count=scan.supported_reference_link_count,
        incomplete_reference_link_count=scan.incomplete_reference_link_count,
        common_reference_link_count=scan.common_reference_link_count,
        separate_reference_link_count=scan.separate_reference_link_count,
        mapped_separate_reference_link_count=scan.mapped_separate_reference_link_count,
        candidate_group_count=scan.candidate_group_count,
    )
