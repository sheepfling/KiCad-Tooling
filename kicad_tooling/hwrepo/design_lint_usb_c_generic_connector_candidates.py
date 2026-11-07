"""Translate USB-C controller and generic connector matches into review candidates."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .design_lint_usb_c_generic_connector_candidate_evidence import (
    UsbCGenericConnectorCandidate,
    UsbCGenericConnectorFindingEvidence,
)
from .netlist_contract_models import NetlistContract
from .usb_c_generic_connector import usb_c_generic_connector_pairs
from .usb_c_ports import UsbCPortRosterContext

RULE_ID: DesignLintRuleId = "bus.usb_c_generic_connector_cc_pair_review"


def generic_connector_usb_c_cc_pair_review_candidates(
    observed: NetlistContract,
    roster: UsbCPortRosterContext,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Prompt when generic connector contacts match both direct controller CC nets."""
    mapped_references: set[str] = set()
    if roster.analysis is not None:
        for port in roster.analysis.ports:
            mapped_references.add(port.connector.casefold())
    findings: list[Candidate] = []
    for pair in usb_c_generic_connector_pairs(observed, reviewed_connector_references):
        if pair.connector_reference.casefold() in mapped_references:
            continue
        evidence = UsbCGenericConnectorFindingEvidence(pair=pair, roster=roster)
        findings.append(
            UsbCGenericConnectorCandidate.from_source_evidence(
                evidence,
                subject=(
                    f"{pair.connector_reference} / {pair.controller_reference}: generic pins "
                    "match USB-C CC1/CC2 nets"
                ),
                message=(
                    "Native assignments place generic connector contacts on both distinct CC1 "
                    "and CC2 nets of one recognized USB-C controller. Review whether this is a "
                    "USB-C port, a test/bring-up connector, or another interface, then record "
                    "the approved pinout and relationship in the project contract. This prompt "
                    "does not identify the connector as USB-C, infer Rp/Rd or port role, require "
                    "the CC nets to be separate or joined, or establish PCB copper or continuity."
                ),
            )
        )
    return tuple(findings)
