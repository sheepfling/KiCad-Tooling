"""Translate generic connector USB pin assignments into review candidates."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .design_lint_usb_generic_connector_candidate_evidence import (
    UsbGenericConnectorCandidate,
    UsbGenericConnectorFindingEvidence,
)
from .netlist_contract_models import NetlistContract
from .usb_peer_generic_connector_candidates import generic_usb_connector_data_pair_candidates
from .usb_peer_map_identity import usb_data_interface_matches_endpoint_group

RULE_ID: DesignLintRuleId = "bus.usb_generic_connector_phy_pair_review"


def generic_usb_connector_phy_pair_review_candidates(
    observed: NetlistContract,
    data_path: UsbDataPathCandidateInputs,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Request map review for generic connector contacts matching one USB PHY pair."""
    found: list[Candidate] = []
    for pair in generic_usb_connector_data_pair_candidates(observed, reviewed_connector_references):
        if _has_endpoint_map(
            data_path, pair.connector_reference, pair.phy_reference, pair.port_group
        ):
            continue
        port = f" port {pair.port_group}" if pair.port_group is not None else ""
        evidence = UsbGenericConnectorFindingEvidence(pair=pair, data_path=data_path)
        found.append(
            UsbGenericConnectorCandidate.from_source_evidence(
                evidence,
                subject=(
                    f"{pair.connector_reference} / {pair.phy_reference}: generic pins match "
                    f"USB data nets{port}"
                ),
                message=(
                    "Native assignments place generic connector contacts on both the positive "
                    "and negative data nets of one recognized USB PHY port. Review the connector "
                    "type, exact pinout, and intended interface, then author a USB data-path map "
                    "if applicable. This prompt does not identify the connector as USB, infer "
                    "generic pin functions, prove a data path or PCB copper, or determine how "
                    "power or reference pins should be connected."
                ),
            )
        )
    return tuple(found)


def _has_endpoint_map(
    source: UsbDataPathCandidateInputs,
    connector_reference: str,
    phy_reference: str,
    port_group: str | None,
) -> bool:
    if source.authored_map is None:
        return False
    return any(
        usb_data_interface_matches_endpoint_group(
            interface,
            connector_reference=connector_reference,
            phy_reference=phy_reference,
            port_groups=frozenset({port_group}),
        )
        for interface in source.authored_map.interfaces
    )
