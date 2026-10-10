"""Public compatibility facade for bounded USB peer-reference analysis."""

from .usb_peer_endpoint_analysis import usb_endpoint_reference_pins
from .usb_peer_reference_scan import scan_usb_peer_reference_reviews, usb_peer_reference_reviews
from .usb_peer_reference_types import (
    UsbPeerDataLink,
    UsbPeerDataSeriesResistor,
    UsbPeerDataShuntBranch,
    UsbPeerEndpointGroupCoverage,
    UsbPeerReferenceCoverage,
    UsbPeerReferencePathCoverage,
    UsbPeerReferenceReview,
    UsbPeerReferenceScan,
    UsbReferencePinAssignment,
)

__all__ = [
    "UsbPeerDataLink",
    "UsbPeerDataSeriesResistor",
    "UsbPeerDataShuntBranch",
    "UsbPeerEndpointGroupCoverage",
    "UsbPeerReferenceCoverage",
    "UsbPeerReferencePathCoverage",
    "UsbPeerReferenceReview",
    "UsbPeerReferenceScan",
    "UsbReferencePinAssignment",
    "scan_usb_peer_reference_reviews",
    "usb_endpoint_reference_pins",
    "usb_peer_reference_reviews",
]
