"""Translate unmapped USB series-resistor value differences into REVIEW candidates."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .design_lint_usb_unmapped_series_resistor_value_evidence import (
    USB_UNMAPPED_SERIES_RESISTOR_VALUE_RULE_ID,
    UsbUnmappedSeriesResistorValueCandidate,
    UsbUnmappedSeriesResistorValueFindingEvidence,
)
from .usb_peer_asymmetric_series_path import (
    unmapped_usb_series_resistor_value_mismatches,
)
from .usb_peer_reference_types import UsbPeerReferenceScan

RULE_ID: DesignLintRuleId = USB_UNMAPPED_SERIES_RESISTOR_VALUE_RULE_ID


def usb_unmapped_series_resistor_value_candidates(
    scan: UsbPeerReferenceScan,
    source: UsbDataPathCandidateInputs,
) -> tuple[Candidate, ...]:
    """Ask reviewers to confirm unmapped D+/D- series-resistor value differences."""
    findings: list[Candidate] = []
    for path in unmapped_usb_series_resistor_value_mismatches(scan, source.authored_map):
        link = path.data_link
        positive = link.positive_series_resistor
        negative = link.negative_series_resistor
        if positive is None or negative is None:
            continue
        findings.append(
            UsbUnmappedSeriesResistorValueCandidate.from_source_evidence(
                UsbUnmappedSeriesResistorValueFindingEvidence(path=path, data_path=source),
                subject=(
                    f"{path.connector_reference} / {path.phy_reference}: unmapped USB "
                    "D+/D- series-resistor values differ"
                    + (f" port {link.port_group}" if link.port_group is not None else "")
                ),
                message=(
                    f"The native USB 2.0 path scan finds {positive.reference} at "
                    f"{positive.value} on D+ and {negative.reference} at {negative.value} "
                    "on D-, but no current connector/PHY map covers this port group. "
                    "Review whether the nominal values are intentionally different and "
                    "record the selected ranges. This prompt does not say either value is "
                    "wrong or establish resistor tolerance, signal integrity, USB compliance, "
                    "component conduction, PCB copper continuity, or a defect."
                ),
            )
        )
    return tuple(findings)
