"""Find unmapped USB 2.0 pairs with a series resistor on only one data line."""

from __future__ import annotations

from .resistor_paths import resistance_ohms
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_map_identity import usb_data_path_map_matches_peer_path
from .usb_peer_reference_types import UsbPeerReferencePathCoverage, UsbPeerReferenceScan


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
            or usb_data_path_map_matches_peer_path(path_map, path)
        ):
            continue
        candidates.append(path)
    return tuple(candidates)


def unmapped_usb_series_resistor_value_mismatches(
    scan: UsbPeerReferenceScan,
    path_map: UsbDataPathMap | None,
) -> tuple[UsbPeerReferencePathCoverage, ...]:
    """Return complete USB 2.0 pairs with different parsed series-resistor values.

    A current endpoint map owns the path's component identities and nominal
    value ranges. Without one, this is only a REVIEW cue for the project to
    decide whether the two observed resistor values are intentional.
    """
    candidates: list[UsbPeerReferencePathCoverage] = []
    for path in scan.coverage.path_entries:
        link = path.data_link
        positive = link.positive_series_resistor
        negative = link.negative_series_resistor
        if (
            link.connector_signal_family != "USB 2.0 data"
            or link.phy_signal_family != "USB 2.0 data"
            or positive is None
            or negative is None
            or usb_data_path_map_matches_peer_path(path_map, path)
        ):
            continue
        positive_ohms = resistance_ohms(positive.value)
        negative_ohms = resistance_ohms(negative.value)
        if (
            positive_ohms is not None
            and negative_ohms is not None
            and positive_ohms != negative_ohms
        ):
            candidates.append(path)
    return tuple(candidates)
