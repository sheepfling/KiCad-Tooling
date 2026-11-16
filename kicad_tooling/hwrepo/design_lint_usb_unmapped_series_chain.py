"""Translate unmapped USB series-chain observations into REVIEW candidates."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .design_lint_usb_unmapped_series_chain_candidate_evidence import (
    USB_UNMAPPED_SERIES_CHAIN_RULE_ID,
    UsbUnmappedSeriesChainCandidate,
    UsbUnmappedSeriesChainFindingEvidence,
)
from .netlist_contract_models import NetlistContract
from .usb_peer_unsupported_series_chain import unsupported_usb_series_chain_candidates

RULE_ID: DesignLintRuleId = USB_UNMAPPED_SERIES_CHAIN_RULE_ID


def usb_unmapped_series_chain_candidates(
    observed: NetlistContract,
    source: UsbDataPathCandidateInputs,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Request review when a fully observed USB resistor chain lacks a map."""
    return tuple(
        UsbUnmappedSeriesChainCandidate.from_source_evidence(
            UsbUnmappedSeriesChainFindingEvidence(path=path, data_path=source),
            subject=(
                f"{path.connector_reference} / {path.phy_reference}: "
                "unmapped USB multi-stage series chain"
                + (f" port {path.port_group}" if path.port_group is not None else "")
            ),
            message=(
                "Native pin assignments form an unbranched USB 2.0 D+/D- path with multiple "
                "fitted two-pin Device:R stages on at least one line, but no exact current USB "
                "data-path map covers this connector/PHY port group. Review the project intent "
                "and document the chain or its unsupported coverage status. The current map "
                "schema cannot express multiple stages. This prompt does not establish resistor "
                "suitability, component conduction, PCB copper, off-board continuity, or a defect."
            ),
        )
        for path in unsupported_usb_series_chain_candidates(
            observed,
            source.authored_map,
            reviewed_connector_references,
        )
    )
