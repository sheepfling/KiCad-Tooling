"""Find unmapped USB 2.0 pairs with a series resistor on only one data line."""

from __future__ import annotations

from .usb_data_path_models import UsbDataPathMap
from .usb_peer_map_identity import usb_data_interface_matches_endpoint_group
from .usb_peer_reference_types import UsbPeerReferencePathCoverage, UsbPeerReferenceScan


def _has_current_endpoint_map(
    path: UsbPeerReferencePathCoverage,
    path_map: UsbDataPathMap | None,
) -> bool:
    if path_map is None:
        return False
    groups = {path.data_link.port_group}
    return any(
        usb_data_interface_matches_endpoint_group(
            interface,
            connector_reference=path.connector_reference,
            phy_reference=path.phy_reference,
            port_groups=groups,
        )
        for interface in path_map.interfaces
    )


def unmapped_usb_asymmetric_series_paths(
    scan: UsbPeerReferenceScan,
    path_map: UsbDataPathMap | None,
) -> tuple[UsbPeerReferencePathCoverage, ...]:
    """Return complete USB 2.0 paths with a resistor on exactly one data line.

    The source-bound peer scan has already established unique endpoint pins,
    direct or single-resistor paths, complete fitted resistor inventories, and
    exact net membership. This predicate adds only the line-to-line comparison.
    An exact endpoint map delegates any topology mismatch to the mapped-path
    rule and suppresses this coverage prompt.
    """
    candidates: list[UsbPeerReferencePathCoverage] = []
    for path in scan.coverage.path_entries:
        link = path.data_link
        if (
            link.connector_signal_family != "USB 2.0 data"
            or link.phy_signal_family != "USB 2.0 data"
            or (link.positive_series_resistor is None) == (link.negative_series_resistor is None)
            or _has_current_endpoint_map(path, path_map)
        ):
            continue
        candidates.append(path)
    return tuple(candidates)
