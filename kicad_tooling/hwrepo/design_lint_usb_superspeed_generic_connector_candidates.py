"""Review generic connector contacts on native USB SuperSpeed PHY pairs."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .design_lint_usb_superspeed_generic_connector_candidate_evidence import (
    UsbSuperspeedGenericConnectorCandidate,
    UsbSuperspeedGenericConnectorFindingEvidence,
)
from .netlist_contract_models import NetlistContract
from .usb_peer_generic_connector_candidates import (
    generic_usb_connector_superspeed_pair_candidates,
)

RULE_ID: DesignLintRuleId = "bus.usb_superspeed_generic_connector_pair_review"


def generic_usb_superspeed_connector_pair_review_candidates(
    observed: NetlistContract,
    data_path: UsbDataPathCandidateInputs,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Prompt review for unmapped generic connector contacts on a native SS pair."""
    found: list[Candidate] = []
    for pair in generic_usb_connector_superspeed_pair_candidates(
        observed, reviewed_connector_references
    ):
        if _has_endpoint_map(
            data_path, pair.connector_reference, pair.phy_reference, pair.signal_family
        ):
            continue
        found.append(
            UsbSuperspeedGenericConnectorCandidate.from_source_evidence(
                UsbSuperspeedGenericConnectorFindingEvidence(pair=pair, data_path=data_path)
            )
        )
    return tuple(found)


def _has_endpoint_map(
    source: UsbDataPathCandidateInputs,
    connector_reference: str,
    phy_reference: str,
    phy_signal_family: str,
) -> bool:
    if source.authored_map is None:
        return False
    connector_signal_family = (
        "USB SuperSpeed RX" if phy_signal_family == "USB SuperSpeed TX" else "USB SuperSpeed TX"
    )
    return any(
        item.connector_reference.casefold() == connector_reference.casefold()
        and item.phy_reference.casefold() == phy_reference.casefold()
        and item.connector_signal_family == connector_signal_family
        and item.phy_signal_family == phy_signal_family
        for item in source.authored_map.superspeed_interfaces
    )
