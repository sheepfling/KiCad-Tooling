"""Review unsupported multi-pin USB data topologies without asserting a path."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .design_lint_usb_unmapped_topology_candidate_evidence import (
    USB_UNMAPPED_TOPOLOGY_RULE_ID,
    UsbUnmappedMultiPinTopologyCandidate,
    UsbUnmappedMultiPinTopologyFindingEvidence,
)
from .usb_peer_map_identity import usb_data_interface_matches_endpoint_group
from .usb_peer_reference_types import UsbPeerReferenceScan, UsbPeerUnsupportedMultiPinPath

RULE_ID: DesignLintRuleId = USB_UNMAPPED_TOPOLOGY_RULE_ID


def _has_endpoint_map(
    source: UsbDataPathCandidateInputs, path: UsbPeerUnsupportedMultiPinPath
) -> bool:
    if source.authored_map is None:
        return False
    return any(
        usb_data_interface_matches_endpoint_group(
            item,
            connector_reference=path.connector_reference,
            phy_reference=path.phy_reference,
            port_groups=frozenset({path.port_group}),
        )
        for item in source.authored_map.interfaces
    )


def usb_unmapped_multi_pin_topology_candidates(
    scan: UsbPeerReferenceScan,
    source: UsbDataPathCandidateInputs,
) -> tuple[Candidate, ...]:
    """Ask for a map when observed multi-pin assignments cannot support a USB path."""
    candidates: list[Candidate] = []
    for path in scan.coverage.unsupported_multi_pin_paths:
        if _has_endpoint_map(source, path):
            continue
        port = f" port {path.port_group}" if path.port_group is not None else ""
        topology_text = (
            "unmapped USB multi-pin data attachment"
            if path.topology == "shared_data_net_attachment"
            else "unmapped USB multi-pin topology"
        )
        topology_message = (
            "Native pin assignments place one fitted multi-pin component on both shared USB 2.0 "
            "D+/D- nets, but no exact current USB data-path map covers it. Review the exact "
            "part pinout and map the part where appropriate, or document why this attachment "
            "remains outside coverage. This prompt does not identify the component's function, "
            "assert a data path, or establish a defect."
            if path.topology == "shared_data_net_attachment"
            else "Native pin assignments place one multi-pin component on connector-side and "
            "PHY-side USB 2.0 D+/D- nets, but do not establish a data path. Review the exact "
            "part pinout and provide a project-authored USB data-path map for this "
            "connector/PHY port group, or document why this topology remains outside coverage. "
            "This prompt does not assert component conduction, a confirmed path, a defect, or a "
            "required common reference."
        )
        candidates.append(
            UsbUnmappedMultiPinTopologyCandidate.from_source_evidence(
                UsbUnmappedMultiPinTopologyFindingEvidence(path=path, data_path=source),
                subject=(
                    f"{path.connector_reference} / {path.phy_reference}: {topology_text}"
                    f"{port} ({path.component_reference})"
                ),
                message=topology_message,
            )
        )
    return tuple(candidates)
