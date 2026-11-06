"""Coordinate USB data-path, connector, and USB-C peer review candidates."""

from __future__ import annotations

from .design_lint_types import Candidate
from .design_lint_usb_c_candidates import (
    usb_c_port_candidates,
    usb_c_vbus_capacitance_candidates,
)
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .design_lint_usb_generic_connector_candidates import (
    generic_usb_connector_phy_pair_review_candidates,
)
from .design_lint_usb_peer_candidates import usb_peer_reference_candidates
from .design_lint_usb_superspeed_generic_connector_candidates import (
    generic_usb_superspeed_connector_pair_review_candidates,
)
from .design_lint_usb_unmapped_topology import usb_unmapped_multi_pin_topology_candidates
from .netlist_contract_models import NetlistContract
from .usb_c_ports import UsbCPortRosterContext
from .usb_peer_data_crossing import usb_peer_data_pair_crossing_candidates
from .usb_peer_reference_scan import UsbPeerReferenceScan


def usb_peer_group_candidates(
    observed: NetlistContract,
    reference_scan: UsbPeerReferenceScan,
    data_path: UsbDataPathCandidateInputs,
    reviewed_connector_references: tuple[str, ...],
) -> tuple[Candidate, ...]:
    """Return USB candidates while keeping peer-dispatch details in the USB theme."""
    return (
        *usb_peer_data_pair_crossing_candidates(
            observed,
            data_path.authored_map,
            reviewed_connector_references,
        ),
        *usb_peer_reference_candidates(reference_scan, data_path),
        *generic_usb_connector_phy_pair_review_candidates(
            observed,
            data_path,
            reviewed_connector_references,
        ),
        *generic_usb_superspeed_connector_pair_review_candidates(
            observed,
            data_path,
            reviewed_connector_references,
        ),
        *usb_unmapped_multi_pin_topology_candidates(reference_scan, data_path),
    )


def usb_c_peer_candidates(
    observed: NetlistContract,
    roster: UsbCPortRosterContext,
    reviewed_connector_references: tuple[str, ...],
) -> tuple[Candidate, ...]:
    """Return USB-C candidates at their established peer-report position."""
    return (
        *usb_c_port_candidates(observed, roster, reviewed_connector_references),
        *usb_c_vbus_capacitance_candidates(observed, roster, reviewed_connector_references),
    )
