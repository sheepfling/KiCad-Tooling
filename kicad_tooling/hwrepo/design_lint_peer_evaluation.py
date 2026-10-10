"""Collect source-bound peer evidence used by interface and connector heuristics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .component_peer_pin_scan import (
    ComponentPeerPinAssignmentScans,
    component_peer_pin_assignment_scans,
)
from .design_lint_peer_candidates import DigitalPeerVoltageLintContext
from .design_lint_peer_coverage import (
    digital_peer_voltage_coverage,
    serial_peer_reference_coverage,
    usb_peer_reference_coverage,
)
from .design_lint_rule_types import DesignLintRuleId
from .digital_peer_voltage_models import DigitalPeerVoltageRuleCoverage
from .digital_peer_voltage_scan import scan_digital_peer_voltage_reviews
from .digital_peer_voltage_types import DigitalPeerVoltageScan
from .models import (
    ConnectorCoverageReport,
    DesignLintRuleOverride,
    Digest,
    NetlistContract,
    UsbDataPathMap,
)
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_models import SerialPeerReferenceCoverageReport
from .serial_peer_reference_scan import scan_serial_peer_reference_reviews
from .serial_peer_reference_types import SerialPeerReferenceScan
from .usb_peer_reference_models import UsbPeerReferenceCoverageReport
from .usb_peer_reference_scan import scan_usb_peer_reference_reviews
from .usb_peer_reference_types import UsbPeerReferenceScan


@dataclass(frozen=True)
class PeerDesignLintEvidence:
    """Source-bound peer scans and their current policy coverage summaries."""

    digital_peer_voltage_scan: DigitalPeerVoltageScan
    digital_peer_voltage_coverage: tuple[DigitalPeerVoltageRuleCoverage, ...]
    reviewed_connector_references: tuple[str, ...]
    peer_pin_assignment_scans: ComponentPeerPinAssignmentScans
    usb_peer_reference_scan: UsbPeerReferenceScan
    usb_peer_reference_coverage: UsbPeerReferenceCoverageReport | None
    serial_peer_reference_scan: SerialPeerReferenceScan
    serial_peer_reference_coverage: SerialPeerReferenceCoverageReport | None


def scan_peer_design_lint_evidence(
    *,
    observed: NetlistContract,
    netlist_sha256: Digest | None,
    connector_coverage: ConnectorCoverageReport | None,
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None,
    serial_peer_roster: SerialPeerRosterContext | None,
    usb_data_path_map: UsbDataPathMap | None,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
) -> PeerDesignLintEvidence:
    """Scan the peer interface families once and bind their applicability evidence."""
    peer_voltage_scope = digital_peer_voltage_context or DigitalPeerVoltageLintContext(
        state="not_configured"
    )
    digital_scan = scan_digital_peer_voltage_reviews(observed, peer_voltage_scope.analysis)
    digital_coverage = (
        ()
        if netlist_sha256 is None
        else digital_peer_voltage_coverage(
            digital_scan,
            peer_voltage_scope,
            default_modes,
            overrides,
            netlist_sha256,
        )
    )
    reviewed_references = (
        tuple(
            entry.reference
            for entry in connector_coverage.entries
            if entry.interface_id is not None
        )
        if connector_coverage is not None
        else ()
    )
    pin_scans = component_peer_pin_assignment_scans(observed, reviewed_references)
    usb_scan = scan_usb_peer_reference_reviews(
        observed,
        usb_data_path_map,
        reviewed_references,
    )
    usb_coverage = (
        None
        if netlist_sha256 is None
        else usb_peer_reference_coverage(
            usb_scan,
            default_modes,
            overrides,
            netlist_sha256,
            usb_data_path_map,
        )
    )
    serial_scope = serial_peer_roster or SerialPeerRosterContext(state="not_configured")
    serial_scan = scan_serial_peer_reference_reviews(
        observed,
        serial_scope.analysis,
        reviewed_references,
    )
    serial_coverage = (
        None
        if netlist_sha256 is None
        else serial_peer_reference_coverage(
            serial_scan,
            serial_scope,
            default_modes,
            overrides,
            netlist_sha256,
        )
    )
    return PeerDesignLintEvidence(
        digital_peer_voltage_scan=digital_scan,
        digital_peer_voltage_coverage=digital_coverage,
        reviewed_connector_references=reviewed_references,
        peer_pin_assignment_scans=pin_scans,
        usb_peer_reference_scan=usb_scan,
        usb_peer_reference_coverage=usb_coverage,
        serial_peer_reference_scan=serial_scan,
        serial_peer_reference_coverage=serial_coverage,
    )
