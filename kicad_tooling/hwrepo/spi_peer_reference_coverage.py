"""Bind SPI shared-clock reference observations to lint policy and findings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .models import DesignLintRuleOverride
from .spi_peer_reference_models import (
    SpiClockPeerCoverage,
    SpiPeerReferenceCoverageReport,
)
from .spi_peer_reference_scan import SpiPeerReferenceScan


def spi_peer_reference_coverage(
    scan: SpiPeerReferenceScan,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
    candidate_clock_keys: frozenset[str] | None = None,
) -> SpiPeerReferenceCoverageReport:
    """Count shared-clock applicability and component-peer duplicate coverage."""
    rule_id: Literal["bus.spi_peer_reference_review"] = "bus.spi_peer_reference_review"
    mode = overrides.get(rule_id)
    resolved_mode = default_modes[rule_id] if mode is None else mode.mode
    entries = tuple(
        SpiClockPeerCoverage(
            clock_net=bus.clock_net,
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
                if candidate_clock_keys is not None
                and bus.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
                and bus.clock_net.casefold() not in candidate_clock_keys
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
    status: Literal["NO_SHARED_CLOCK_PEERS", "INCOMPLETE", "EVALUATED"] = (
        "NO_SHARED_CLOCK_PEERS"
        if not entries
        else "INCOMPLETE"
        if incomplete_count
        else "EVALUATED"
    )
    return SpiPeerReferenceCoverageReport(
        rule_id=rule_id,
        status=status,
        mode=resolved_mode,
        netlist_sha256=netlist_sha256,
        recognized_endpoint_count=scan.recognized_endpoint_count,
        shared_clock_bus_count=len(entries),
        common_reference_bus_count=sum(item.disposition == "COMMON_REFERENCE" for item in entries),
        incomplete_reference_bus_count=incomplete_count,
        split_reference_bus_count=split_count,
        candidate_group_count=candidate_count,
        component_peer_covered_bus_count=sum(
            item.disposition == "COMPONENT_PEER_REVIEW_COVERS" for item in entries
        ),
        entries=entries,
    )
