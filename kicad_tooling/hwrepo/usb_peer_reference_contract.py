"""Match observed USB endpoint paths against project-authored maps."""

from __future__ import annotations

from .usb_data_path_models import (
    UsbDataInterfaceRequirement,
    UsbDataPathInlineComponentRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
)
from .usb_peer_reference_types import (
    UsbEndpoint,
    UsbPeerDataInlineComponent,
    UsbPeerDataLink,
    UsbPeerDataSeriesResistor,
)


def _mapped_line_matches(
    requirement: UsbDataPathLineRequirement,
    connector_pins: tuple[str, ...],
    phy_pins: tuple[str, ...],
    connector_net: str,
    phy_net: str,
    series_resistor: UsbPeerDataSeriesResistor | None,
    inline_component: UsbPeerDataInlineComponent | None,
    inline_requirement: UsbDataPathInlineComponentRequirement | None,
    *,
    positive: bool,
) -> bool:
    expected_topology = (
        "inline_component"
        if inline_component is not None
        else "series_resistor"
        if series_resistor is not None
        else "direct"
    )
    if (
        requirement.topology != expected_topology
        or {pin.casefold() for pin in requirement.connector_pins}
        != {pin.casefold() for pin in connector_pins}
        or {pin.casefold() for pin in requirement.phy_pins} != {pin.casefold() for pin in phy_pins}
        or requirement.connector_net.casefold() != connector_net.casefold()
        or requirement.phy_net.casefold() != phy_net.casefold()
    ):
        return False
    mapped_resistor = requirement.series_resistor
    if series_resistor is None:
        if mapped_resistor is not None:
            return False
    elif (
        mapped_resistor is None
        or mapped_resistor.reference.casefold() != series_resistor.reference.casefold()
        or mapped_resistor.expected_symbol != series_resistor.symbol
        or mapped_resistor.expected_footprint != series_resistor.footprint
    ):
        return False
    if inline_component is None:
        return inline_requirement is None
    if inline_requirement is None:
        return False
    connector_pin = (
        inline_requirement.positive_connector_pin
        if positive
        else inline_requirement.negative_connector_pin
    )
    phy_pin = (
        inline_requirement.positive_phy_pin if positive else inline_requirement.negative_phy_pin
    )
    expected_assignments = {
        (
            f"{item.pin}={item.net}" if item.disposition == "net" else f"{item.pin}=<unconnected>"
        ).casefold()
        for item in inline_requirement.pins
    }
    return (
        inline_component.reference.casefold() == inline_requirement.reference.casefold()
        and inline_component.symbol == inline_requirement.expected_symbol
        and inline_component.footprint == inline_requirement.expected_footprint
        and inline_component.connector_pin.casefold() == connector_pin.casefold()
        and inline_component.phy_pin.casefold() == phy_pin.casefold()
        and inline_component.connector_net.casefold() == connector_net.casefold()
        and inline_component.phy_net.casefold() == phy_net.casefold()
        and {item.casefold() for item in inline_component.pin_assignments} == expected_assignments
    )


def _mapped_protection_shunts_match(
    interface: UsbDataInterfaceRequirement,
    data_link: UsbPeerDataLink,
) -> bool:
    requirements = {item.reference.casefold(): item for item in interface.protection_shunts}
    observed = {item.reference.casefold(): item for item in data_link.protection_shunts}
    if requirements.keys() != observed.keys():
        return False
    for reference, requirement in requirements.items():
        component = observed[reference]
        expected_pins = {
            (item.line, item.pin.casefold(), item.net.casefold()) for item in requirement.data_pins
        }
        actual_pins = {
            (item.line, item.pin.casefold(), item.net.casefold()) for item in component.data_pins
        }
        expected_assignments = {
            (
                f"{item.pin}={item.net}"
                if item.disposition == "net"
                else f"{item.pin}=<unconnected>"
            ).casefold()
            for item in requirement.pins
        }
        if (
            component.symbol != requirement.expected_symbol
            or component.footprint != requirement.expected_footprint
            or expected_pins != actual_pins
            or expected_assignments != {item.casefold() for item in component.pin_assignments}
        ):
            return False
    return True


def usb_reference_map_matches(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    data_link: UsbPeerDataLink,
    path_map: UsbDataPathMap | None,
) -> bool:
    """Match a current bounded USB map with an explicit common/separate decision."""
    if (
        path_map is None
        or connector.signal_family != "USB 2.0 data"
        or phy.signal_family != "USB 2.0 data"
    ):
        return False
    observed_connector_references = {item.pin.casefold() for item in connector.reference_pins}
    observed_phy_references = {item.pin.casefold() for item in phy.reference_pins}
    for interface in path_map.interfaces:
        if interface.reference_policy is None:
            continue
        if (
            interface.data_port_group is not None
            and interface.data_port_group != data_link.port_group
        ):
            continue
        if (
            interface.connector_reference.casefold() != connector.reference.casefold()
            or interface.phy_reference.casefold() != phy.reference.casefold()
            or interface.expected_connector_symbol != connector.symbol
            or interface.expected_phy_symbol != phy.symbol
            or interface.expected_connector_footprint != connector.footprint
            or interface.expected_phy_footprint != phy.footprint
            or not _mapped_line_matches(
                interface.positive,
                data_link.connector_positive_pins,
                data_link.phy_positive_pins,
                data_link.connector_positive_net,
                data_link.phy_positive_net,
                data_link.positive_series_resistor,
                data_link.positive_inline_component,
                interface.inline_component,
                positive=True,
            )
            or not _mapped_line_matches(
                interface.negative,
                data_link.connector_negative_pins,
                data_link.phy_negative_pins,
                data_link.connector_negative_net,
                data_link.phy_negative_net,
                data_link.negative_series_resistor,
                data_link.negative_inline_component,
                interface.inline_component,
                positive=False,
            )
            or not _mapped_protection_shunts_match(interface, data_link)
        ):
            continue
        mapped_connector_references = {
            item.pin.casefold() for item in interface.connector_reference_pins
        }
        mapped_phy_references = {item.pin.casefold() for item in interface.phy_reference_pins}
        if (
            mapped_connector_references == observed_connector_references
            and mapped_phy_references == observed_phy_references
        ):
            return True
    return False
