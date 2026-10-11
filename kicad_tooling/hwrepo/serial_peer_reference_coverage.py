"""Source-bound applicability coverage for serial peer-reference checks."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .models import DesignLintRuleOverride
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_models import (
    SerialPeerReferenceCoverageReport,
    SerialPeerReferenceLinkCoverageEntry,
)
from .serial_peer_reference_types import SerialPeerReferenceScan


def serial_peer_reference_coverage(
    scan: SerialPeerReferenceScan,
    context: SerialPeerRosterContext,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
) -> SerialPeerReferenceCoverageReport:
    """Bind serial reference applicability counts to the native source and policy."""
    rule_id: Literal["bus.serial_peer_reference_review"] = "bus.serial_peer_reference_review"
    mode = default_modes[rule_id]
    if override := overrides.get(rule_id):
        mode = override.mode
    discovered = scan.native_peer_link_count + scan.label_peer_link_count
    status: Literal["NO_DIRECT_PEERS", "INCOMPLETE", "EVALUATED"] = (
        "NO_DIRECT_PEERS"
        if discovered == 0
        else "INCOMPLETE"
        if scan.incomplete_reference_link_count > 0
        else "EVALUATED"
    )
    map_sha256 = (
        hashlib.sha256(context.analysis.model_dump_json().encode("utf-8")).hexdigest()
        if context.analysis is not None
        else None
    )
    return SerialPeerReferenceCoverageReport(
        rule_id=rule_id,
        status=status,
        mode=mode,
        netlist_sha256=netlist_sha256,
        authored_map_state=context.state,
        authored_map_path=context.source_path,
        authored_map_source_sha256=context.source_sha256,
        authored_serial_peer_map_sha256=map_sha256,
        link_entries=tuple(
            SerialPeerReferenceLinkCoverageEntry(
                discovery_basis=entry.discovery_basis,
                first_reference=entry.first_reference,
                second_reference=entry.second_reference,
                signal_group=entry.signal_group,
                signal_nets=entry.signal_nets,
                signal_pins=entry.signal_pins,
                disposition=entry.disposition,
            )
            for entry in scan.link_entries
        ),
        native_peer_link_count=scan.native_peer_link_count,
        label_peer_link_count=scan.label_peer_link_count,
        supported_reference_link_count=scan.supported_reference_link_count,
        incomplete_reference_link_count=scan.incomplete_reference_link_count,
        common_reference_link_count=scan.common_reference_link_count,
        separate_reference_link_count=scan.separate_reference_link_count,
        mapped_separate_reference_link_count=scan.mapped_separate_reference_link_count,
        candidate_group_count=scan.candidate_group_count,
    )
