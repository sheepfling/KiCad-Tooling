"""Source-bound applicability coverage for digital peer voltage checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .digital_peer_voltage_models import DigitalPeerVoltageRuleCoverage
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan
from .models import DesignLintRuleOverride


def digital_peer_voltage_coverage(
    scan: DigitalPeerVoltageScan,
    context: DigitalPeerVoltageLintContext,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
) -> tuple[DigitalPeerVoltageRuleCoverage, ...]:
    """Bind bounded peer-voltage applicability counts to their sources and policy."""
    result: list[DigitalPeerVoltageRuleCoverage] = []
    for item in scan.coverage:
        rule_id: Literal["bus.spi_peer_voltage_review", "bus.serial_peer_voltage_review"] = (
            "bus.spi_peer_voltage_review"
            if item.interface == "SPI"
            else "bus.serial_peer_voltage_review"
        )
        override = overrides.get(rule_id)
        mode = default_modes[rule_id] if override is None else override.mode
        status: Literal["NO_SUPPORTED_ENDPOINTS", "NO_DIRECT_PEERS", "INCOMPLETE", "EVALUATED"] = (
            "NO_SUPPORTED_ENDPOINTS"
            if item.recognized_endpoint_count == 0
            else "INCOMPLETE"
            if item.assigned_endpoint_count < item.recognized_endpoint_count
            or item.voltage_comparison_count < item.direct_peer_link_count
            else "NO_DIRECT_PEERS"
            if item.direct_peer_link_count == 0
            else "EVALUATED"
        )
        result.append(
            DigitalPeerVoltageRuleCoverage(
                rule_id=rule_id,
                status=status,
                mode=mode,
                netlist_sha256=netlist_sha256,
                authored_map_state=context.state,
                authored_map_path=context.source_path,
                authored_map_sha256=context.source_sha256,
                recognized_endpoint_count=item.recognized_endpoint_count,
                assigned_endpoint_count=item.assigned_endpoint_count,
                direct_peer_link_count=item.direct_peer_link_count,
                voltage_comparison_count=item.voltage_comparison_count,
                same_voltage_link_count=item.same_voltage_link_count,
                different_voltage_link_count=item.different_voltage_link_count,
                mapped_mismatch_link_count=item.mapped_mismatch_link_count,
                candidate_group_count=item.review_candidate_group_count,
            )
        )
    return tuple(result)
