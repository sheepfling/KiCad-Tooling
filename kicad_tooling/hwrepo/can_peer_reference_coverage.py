"""Bind CAN peer-reference observations to policy and source coverage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .can_peer_reference_models import (
    CanPeerReferenceBusCoverage,
    CanPeerReferenceCoverageReport,
)
from .can_peer_reference_scan import CanPeerReferenceScan
from .design_lint_finding_models import DesignLintRuleOverride
from .design_lint_rule_types import DesignLintRuleId


def can_peer_reference_coverage(
    scan: CanPeerReferenceScan,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
    candidate_bus_keys: frozenset[tuple[str, str]] | None = None,
) -> CanPeerReferenceCoverageReport:
    """Count shared CAN applicability and component-peer duplicate coverage."""
    rule_id: Literal["bus.can_peer_reference_review"] = "bus.can_peer_reference_review"
    override = overrides.get(rule_id)
    mode = default_modes[rule_id] if override is None else override.mode
    entries = tuple(
        CanPeerReferenceBusCoverage(
            canh_net=bus.canh_net,
            canl_net=bus.canl_net,
            participants=tuple(item.reference for item in bus.endpoints),
            reference_nets=tuple(
                sorted(
                    {
                        item.reference_net
                        for item in bus.endpoints
                        if item.reference_net is not None
                    },
                    key=lambda item: (item.casefold(), item),
                )
            ),
            incomplete_references=bus.incomplete_references,
            disposition=(
                "COMPONENT_PEER_REVIEW_COVERS"
                if candidate_bus_keys is not None
                and bus.disposition == "SPLIT_REFERENCE_REVIEW"
                and (bus.canh_net.casefold(), bus.canl_net.casefold()) not in candidate_bus_keys
                else bus.disposition
            ),
        )
        for bus in scan.buses
    )
    incomplete_count = sum(
        item.disposition in {"INCOMPLETE", "PARTIAL_SPLIT_REFERENCE_REVIEW"} for item in entries
    )
    split_count = sum(
        item.disposition
        in {
            "SPLIT_REFERENCE_REVIEW",
            "PARTIAL_SPLIT_REFERENCE_REVIEW",
            "COMPONENT_PEER_REVIEW_COVERS",
        }
        for item in entries
    )
    candidate_count = sum(
        item.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
        for item in entries
    )
    status: Literal["NO_SHARED_CAN_BUSES", "INCOMPLETE", "EVALUATED"] = (
        "NO_SHARED_CAN_BUSES" if not entries else "INCOMPLETE" if incomplete_count else "EVALUATED"
    )
    return CanPeerReferenceCoverageReport(
        rule_id=rule_id,
        status=status,
        mode=mode,
        netlist_sha256=netlist_sha256,
        recognized_endpoint_count=scan.recognized_endpoint_count,
        shared_can_bus_count=len(entries),
        common_reference_bus_count=sum(item.disposition == "COMMON_REFERENCE" for item in entries),
        incomplete_reference_bus_count=incomplete_count,
        split_reference_bus_count=split_count,
        candidate_group_count=candidate_count,
        component_peer_covered_bus_count=sum(
            item.disposition == "COMPONENT_PEER_REVIEW_COVERS" for item in entries
        ),
        entries=entries,
    )
