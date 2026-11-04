"""Translate USB peer-reference observations and map evidence."""

from __future__ import annotations

from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .design_lint_usb_peer_candidate_evidence import (
    UsbPeerReferenceCandidate,
    UsbPeerReferenceFindingEvidence,
)
from .usb_data_path_models import usb_data_path_map_sha256 as _usb_data_path_map_sha256
from .usb_peer_reference_types import UsbPeerReferenceScan

# Keep the historical helper import path while the map model owns its implementation.
usb_data_path_map_sha256 = _usb_data_path_map_sha256


def usb_peer_reference_candidates(
    usb_scan: UsbPeerReferenceScan,
    usb_data_path: UsbDataPathCandidateInputs,
) -> tuple[Candidate, ...]:
    """Build bounded USB connector-to-PHY reference-domain review prompts."""
    found: list[Candidate] = []
    for peer in usb_scan.reviews:
        is_superspeed = peer.data_link.connector_signal_family.startswith("USB SuperSpeed ")
        subject_signal_label = "USB SuperSpeed" if is_superspeed else "USB"
        message_signal_label = "USB SuperSpeed" if is_superspeed else "USB 2.0 D+/D-"
        topology_description = (
            "one exact direct SuperSpeed complementary pair"
            if is_superspeed
            else "a direct path, one fitted two-pin series resistor, or one exact mapped inline component"
        )
        source_evidence = UsbPeerReferenceFindingEvidence(
            scan=usb_scan,
            review=peer,
            data_path=usb_data_path,
        )
        found.append(
            UsbPeerReferenceCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{peer.connector_reference} / {peer.phy_reference}: "
                    f"{subject_signal_label} reference-domain review"
                    + (
                        f" (port {peer.data_link.port_group})"
                        if peer.data_link.port_group is not None
                        else ""
                    )
                ),
                message=(
                    f"Supported {message_signal_label} connector-to-PHY paths "
                    f"({topology_description}) "
                    "have separate explicit endpoint reference nets. Review whether this interface "
                    "needs a common reference, an "
                    "explicit bond, or intentional isolation. Pin functions and the bounded "
                    "topology only identify a candidate; this prompt does not prove the required "
                    "relationship, component behavior, PCB copper, or off-board continuity."
                ),
            )
        )
    return tuple(found)
