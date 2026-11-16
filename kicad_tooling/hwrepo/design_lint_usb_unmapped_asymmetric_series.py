"""Translate unmapped USB series-path asymmetry into REVIEW candidates."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .design_lint_usb_unmapped_asymmetric_series_candidate_evidence import (
    USB_UNMAPPED_ASYMMETRIC_SERIES_RULE_ID,
    UsbUnmappedAsymmetricSeriesCandidate,
    UsbUnmappedAsymmetricSeriesFindingEvidence,
)
from .usb_peer_asymmetric_series_path import unmapped_usb_asymmetric_series_paths
from .usb_peer_reference_types import UsbPeerReferenceScan

RULE_ID: DesignLintRuleId = USB_UNMAPPED_ASYMMETRIC_SERIES_RULE_ID


def usb_unmapped_asymmetric_series_candidates(
    scan: UsbPeerReferenceScan,
    source: UsbDataPathCandidateInputs,
) -> tuple[Candidate, ...]:
    """Ask for review when a supported USB 2.0 pair has an unmapped split path."""
    findings: list[Candidate] = []
    for path in unmapped_usb_asymmetric_series_paths(scan, source.authored_map):
        link = path.data_link
        series_line = "D+" if link.positive_series_resistor is not None else "D-"
        direct_line = "D-" if series_line == "D+" else "D+"
        findings.append(
            UsbUnmappedAsymmetricSeriesCandidate.from_source_evidence(
                UsbUnmappedAsymmetricSeriesFindingEvidence(path=path, data_path=source),
                subject=(
                    f"{path.connector_reference} / {path.phy_reference}: unmapped USB "
                    "D+/D- series-path asymmetry"
                    + (f" port {link.port_group}" if link.port_group is not None else "")
                ),
                message=(
                    f"The native USB 2.0 path scan finds one fitted two-pin Device:R on "
                    f"{series_line} and a direct path on {direct_line}, but no exact current "
                    "connector/PHY map covers this port group. Review whether that line-level "
                    "difference is intentional and record the selected topology. This prompt "
                    "does not establish resistor suitability, signal integrity, USB compliance, "
                    "component conduction, PCB copper continuity, or a defect."
                ),
            )
        )
    return tuple(findings)
