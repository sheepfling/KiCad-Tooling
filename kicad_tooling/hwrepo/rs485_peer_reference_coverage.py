"""Bind mapped RS-485 peer-reference scans to policy and source coverage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .models import DesignLintRuleOverride
from .rs485_peer_reference_models import (
    Rs485PeerReferenceCoverageReport,
    Rs485PeerReferencePairCoverage,
)
from .rs485_peer_reference_types import Rs485PeerReferenceScan


def rs485_peer_reference_coverage(
    scan: Rs485PeerReferenceScan,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
    candidate_keys: frozenset[tuple[str, str]] | None = None,
) -> Rs485PeerReferenceCoverageReport:
    """Count mapped line-pair applicability, split references, and candidates."""
    rule_id = "bus.rs485_peer_reference_review"
    override = overrides.get(rule_id)
    mode = default_modes[rule_id] if override is None else override.mode
    entries = tuple(
        Rs485PeerReferencePairCoverage(
            bus_id=pair.bus_id,
            pair_id=pair.pair_id,
            line_1_net=pair.line_1_net,
            line_2_net=pair.line_2_net,
            participants=tuple(item.reference for item in pair.endpoints),
            reference_nets=tuple(
                sorted(
                    {
                        item.reference_net
                        for item in pair.endpoints
                        if item.reference_net is not None
                    },
                    key=lambda item: (item.casefold(), item),
                )
            ),
            incomplete_references=pair.incomplete_references,
            disposition=pair.disposition,
        )
        for pair in scan.pairs
    )
    status: Literal[
        "NOT_CONFIGURED",
        "PENDING",
        "NOT_APPLICABLE",
        "NO_SHARED_ENDPOINTS",
        "INCOMPLETE",
        "EVALUATED",
    ]
    if scan.map_state == "not_configured":
        status = "NOT_CONFIGURED"
    elif scan.map_state == "pending":
        status = "PENDING"
    elif scan.map_state == "not_applicable":
        status = "NOT_APPLICABLE"
    elif not entries:
        status = "NO_SHARED_ENDPOINTS"
    elif any(item.incomplete_references for item in entries):
        status = "INCOMPLETE"
    else:
        status = "EVALUATED"
    return Rs485PeerReferenceCoverageReport(
        status=status,
        mode=mode,
        netlist_sha256=netlist_sha256,
        authored_map_state=scan.map_state,
        authored_map_path=scan.source_path,
        authored_map_source_sha256=scan.source_sha256,
        authored_rs485_map_sha256=scan.analysis_sha256,
        recognized_endpoint_count=scan.recognized_endpoint_count,
        shared_pair_count=len(entries),
        common_reference_pair_count=sum(item.disposition == "COMMON_REFERENCE" for item in entries),
        incomplete_reference_pair_count=sum(
            item.disposition in {"INCOMPLETE", "PARTIAL_SPLIT_REFERENCE_REVIEW"} for item in entries
        ),
        split_reference_pair_count=sum(
            item.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
            for item in entries
        ),
        candidate_group_count=sum(
            item.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
            and (
                candidate_keys is None
                or (item.bus_id.casefold(), item.pair_id.casefold()) in candidate_keys
            )
            for item in entries
        ),
        entries=entries,
    )
