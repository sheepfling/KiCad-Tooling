"""Match observed USB endpoint paths against project-authored maps."""

from __future__ import annotations

from .models import UsbDataPathLineRequirement, UsbDataPathMap
from .usb_peer_reference_types import UsbEndpoint, UsbPeerDataLink, UsbPeerDataSeriesResistor


def _mapped_line_matches(
    requirement: UsbDataPathLineRequirement,
    connector_pins: tuple[str, ...],
    phy_pins: tuple[str, ...],
    connector_net: str,
    phy_net: str,
    series_resistor: UsbPeerDataSeriesResistor | None,
) -> bool:
    if (
        requirement.topology != ("series_resistor" if series_resistor is not None else "direct")
        or {pin.casefold() for pin in requirement.connector_pins}
        != {pin.casefold() for pin in connector_pins}
        or {pin.casefold() for pin in requirement.phy_pins} != {pin.casefold() for pin in phy_pins}
        or requirement.connector_net.casefold() != connector_net.casefold()
        or requirement.phy_net.casefold() != phy_net.casefold()
    ):
        return False
    mapped_resistor = requirement.series_resistor
    if series_resistor is None:
        return mapped_resistor is None
    return (
        mapped_resistor is not None
        and mapped_resistor.reference.casefold() == series_resistor.reference.casefold()
        and mapped_resistor.expected_symbol == series_resistor.symbol
        and mapped_resistor.expected_footprint == series_resistor.footprint
    )


def usb_reference_map_matches(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    data_link: UsbPeerDataLink,
    path_map: UsbDataPathMap | None,
) -> bool:
    """Match a current bounded USB map with an explicit common/separate decision."""
    if path_map is None:
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
            )
            or not _mapped_line_matches(
                interface.negative,
                data_link.connector_negative_pins,
                data_link.phy_negative_pins,
                data_link.connector_negative_net,
                data_link.phy_negative_net,
                data_link.negative_series_resistor,
            )
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
