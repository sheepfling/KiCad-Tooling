"""Source-bound applicability coverage for I2C peer-reference checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .i2c_peer_reference_models import (
    I2cPeerReferenceBusCoverage,
    I2cPeerReferenceCoverageReport,
)
from .i2c_peer_reference_scan import I2cPeerReferenceScan
from .models import DesignLintRuleOverride


def i2c_peer_reference_coverage(
    scan: I2cPeerReferenceScan,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
    candidate_bus_keys: frozenset[tuple[str, str]] | None = None,
) -> I2cPeerReferenceCoverageReport:
    """Bind shared-bus I2C reference applicability counts to native evidence."""
    rule_id: Literal["bus.i2c_peer_reference_review"] = "bus.i2c_peer_reference_review"
    mode = default_modes[rule_id]
    if override := overrides.get(rule_id):
        mode = override.mode
    entries = tuple(
        I2cPeerReferenceBusCoverage(
            sda_net=bus.sda_net,
            scl_net=bus.scl_net,
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
                and bus.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
                and (bus.sda_net.casefold(), bus.scl_net.casefold()) not in candidate_bus_keys
                else bus.disposition
            ),
        )
        for bus in scan.buses
    )
    incomplete_bus_count = sum(
        item.disposition in {"INCOMPLETE", "PARTIAL_SPLIT_REFERENCE_REVIEW"} for item in entries
    )
    split_bus_count = sum(
        item.disposition
        in {
            "SPLIT_REFERENCE_REVIEW",
            "PARTIAL_SPLIT_REFERENCE_REVIEW",
            "COMPONENT_PEER_REVIEW_COVERS",
        }
        for item in entries
    )
    candidate_bus_count = sum(
        item.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
        for item in entries
    )
    status: Literal["NO_SHARED_BUS_PEERS", "INCOMPLETE", "EVALUATED"] = (
        "NO_SHARED_BUS_PEERS"
        if not entries
        else "INCOMPLETE"
        if incomplete_bus_count
        else "EVALUATED"
    )
    return I2cPeerReferenceCoverageReport(
        rule_id=rule_id,
        status=status,
        mode=mode,
        netlist_sha256=netlist_sha256,
        recognized_endpoint_count=scan.recognized_endpoint_count,
        shared_bus_count=len(entries),
        common_reference_bus_count=sum(item.disposition == "COMMON_REFERENCE" for item in entries),
        incomplete_reference_bus_count=incomplete_bus_count,
        split_reference_bus_count=split_bus_count,
        candidate_group_count=candidate_bus_count,
        component_peer_covered_bus_count=sum(
            item.disposition == "COMPONENT_PEER_REVIEW_COVERS" for item in entries
        ),
        entries=entries,
    )
