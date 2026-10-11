"""Source-bound applicability coverage for USB peer-reference checks."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .models import DesignLintRuleOverride
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_reference_models import (
    UsbPeerDataInlineComponentCoverage,
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
    UsbPeerDataInlineComponent,
    UsbPeerDataSeriesResistor,
    UsbPeerDataShuntBranch,
    UsbPeerReferencePathCoverage,
    UsbPeerReferenceScan,
)


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
        inline_component: UsbPeerDataInlineComponent | None,
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
        inline = (
            None
            if inline_component is None
            else UsbPeerDataInlineComponentCoverage(
                reference=inline_component.reference,
                symbol=inline_component.symbol,
                footprint=inline_component.footprint,
                connector_pin=inline_component.connector_pin,
                phy_pin=inline_component.phy_pin,
                connector_net=inline_component.connector_net,
                phy_net=inline_component.phy_net,
                pin_assignments=inline_component.pin_assignments,
            )
        )
        return UsbPeerDataLineCoverage(
            connector_pins=connector_pins,
            phy_pins=phy_pins,
            connector_net=connector_net,
            phy_net=phy_net,
            series_resistor=resistor,
            inline_component=inline,
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
                link.positive_inline_component,
                link.positive_shunt_branches,
            ),
            negative=data_line(
                link.connector_negative_pins,
                link.phy_negative_pins,
                link.connector_negative_net,
                link.phy_negative_net,
                link.negative_series_resistor,
                link.negative_inline_component,
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
