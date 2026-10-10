"""Coverage records for project-mapped USB and power topologies."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import (
    DesignLintMappedCheckRun,
    DesignLintPolicy,
    PowerPathMap,
    PowerSequenceMap,
    UsbDataPathMap,
)

MappedTopologyRuleId = Literal[
    "bus.usb_data_path_mismatch",
    "power.mapped_series_path_mismatch",
    "power.mapped_sequence_dependency_mismatch",
]
RuleMode = Literal["review", "block", "off"]


def _mapped_check_run(
    rule_id: MappedTopologyRuleId,
    map_sha256: str | None,
    requirement_count: int,
    netlist_sha256: str | None,
    candidates: Sequence[Candidate],
    mode: RuleMode,
) -> DesignLintMappedCheckRun:
    finding_count = sum(item.rule_id == rule_id for item in candidates)
    if map_sha256 is None:
        return DesignLintMappedCheckRun(
            rule_id=rule_id,
            status="NOT_CONFIGURED",
            mode=mode,
            netlist_sha256=netlist_sha256,
            reason="No project-authored map was supplied for this check.",
        )
    if netlist_sha256 is None:
        return DesignLintMappedCheckRun(
            rule_id=rule_id,
            status="BLOCKED",
            mode=mode,
            map_sha256=map_sha256,
            requirement_count=requirement_count,
            finding_count=finding_count,
            reason="The evaluated netlist had no source-bound SHA-256.",
        )
    return DesignLintMappedCheckRun(
        rule_id=rule_id,
        status="EVALUATED",
        mode=mode,
        map_sha256=map_sha256,
        netlist_sha256=netlist_sha256,
        requirement_count=requirement_count,
        finding_count=finding_count,
    )


def mapped_topology_coverage_runs(
    policy: DesignLintPolicy,
    default_modes: Mapping[DesignLintRuleId, RuleMode],
    candidates: Sequence[Candidate],
    netlist_sha256: str | None,
) -> tuple[DesignLintMappedCheckRun, ...]:
    """Summarize the evaluation state of exact USB, power-path, and sequence maps."""
    overrides = {item.rule_id: item for item in policy.rules}
    usb_rule_id: MappedTopologyRuleId = "bus.usb_data_path_mismatch"
    power_path_rule_id: MappedTopologyRuleId = "power.mapped_series_path_mismatch"
    power_sequence_rule_id: MappedTopologyRuleId = "power.mapped_sequence_dependency_mismatch"
    usb_map: UsbDataPathMap | None = policy.usb_data_path_map
    power_path_map: PowerPathMap | None = policy.power_path_map
    power_sequence_map: PowerSequenceMap | None = policy.power_sequence_map
    return (
        _mapped_check_run(
            usb_rule_id,
            None
            if usb_map is None
            else hashlib.sha256(usb_map.model_dump_json().encode("utf-8")).hexdigest(),
            0 if usb_map is None else len(usb_map.interfaces),
            netlist_sha256,
            candidates,
            default_modes[usb_rule_id]
            if usb_rule_id not in overrides
            else overrides[usb_rule_id].mode,
        ),
        _mapped_check_run(
            power_path_rule_id,
            None
            if power_path_map is None
            else hashlib.sha256(power_path_map.model_dump_json().encode("utf-8")).hexdigest(),
            0 if power_path_map is None else len(power_path_map.paths),
            netlist_sha256,
            candidates,
            default_modes[power_path_rule_id]
            if power_path_rule_id not in overrides
            else overrides[power_path_rule_id].mode,
        ),
        _mapped_check_run(
            power_sequence_rule_id,
            None
            if power_sequence_map is None
            else hashlib.sha256(power_sequence_map.model_dump_json().encode("utf-8")).hexdigest(),
            0
            if power_sequence_map is None
            else len(power_sequence_map.stages) + len(power_sequence_map.dependencies),
            netlist_sha256,
            candidates,
            default_modes[power_sequence_rule_id]
            if power_sequence_rule_id not in overrides
            else overrides[power_sequence_rule_id].mode,
        ),
    )
