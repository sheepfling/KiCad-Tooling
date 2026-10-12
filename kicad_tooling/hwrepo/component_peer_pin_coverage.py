"""Source-bound applicability coverage for component peer pins."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from .component_peer_pin_models import ComponentPeerPinRuleCoverage
from .component_peer_pin_scan import ComponentPeerPinAssignmentScans, PeerPinAssignmentScan
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import DesignLintRuleOverride


def component_peer_pin_rule_coverage(
    scans: ComponentPeerPinAssignmentScans,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    candidate_items: Sequence[Candidate],
    netlist_sha256: str,
) -> tuple[ComponentPeerPinRuleCoverage, ...]:
    """Bind component-peer pin applicability and findings to one native netlist."""
    rule_scans: tuple[tuple[DesignLintRuleId, PeerPinAssignmentScan], ...] = (
        ("component.peer_power_output_unconnected", scans.power_output),
        ("component.peer_signal_output_unconnected", scans.signal_output),
        ("component.peer_signal_input_unconnected", scans.signal_input),
        ("component.peer_bidirectional_pin_unconnected", scans.bidirectional),
        (
            "component.generic_peer_pin_assignment_outlier",
            scans.generic_assignment_outlier,
        ),
        ("component.generic_peer_pin_mixed_open", scans.generic_partial_open),
        ("component.generic_peer_pin_all_open", scans.generic_all_open),
    )
    result: list[ComponentPeerPinRuleCoverage] = []
    for rule_id, scan in rule_scans:
        peer_group_count = scan.exact_symbol_peer_group_count + scan.part_id_peer_group_count
        if peer_group_count == 0:
            status = (
                "INCOMPLETE_COMPONENT_IDENTITY"
                if scan.part_id_candidate_group_count > 0
                else "NO_COMPARABLE_PEERS"
            )
        elif scan.complete_pin_inventory_group_count == 0:
            status = "INCOMPLETE_PIN_INVENTORY"
        elif scan.matching_electrical_type_pin_group_count == 0:
            status = "NO_MATCHING_PIN_TYPES"
        elif scan.compatible_function_pin_group_count == 0:
            status = "NO_COMPATIBLE_PIN_FUNCTIONS"
        elif scan.unambiguous_assignment_pin_group_count == 0:
            status = "NO_UNAMBIGUOUS_ASSIGNMENTS"
        elif (
            scan.incomplete_pin_inventory_group_count > 0
            or scan.part_id_incomplete_component_identity_group_count > 0
        ):
            status = "PARTIALLY_EVALUATED"
        else:
            status = "EVALUATED"
        override = overrides.get(rule_id)
        finding_count = sum(item.rule_id == rule_id for item in candidate_items)
        candidate_count = len(scan.outliers)
        result.append(
            ComponentPeerPinRuleCoverage(
                rule_id=rule_id,
                status=status,
                mode=default_modes[rule_id] if override is None else override.mode,
                netlist_sha256=netlist_sha256,
                exact_symbol_peer_group_count=scan.exact_symbol_peer_group_count,
                part_id_peer_group_count=scan.part_id_peer_group_count,
                part_id_candidate_group_count=scan.part_id_candidate_group_count,
                part_id_incomplete_component_identity_group_count=(
                    scan.part_id_incomplete_component_identity_group_count
                ),
                part_id_incomplete_component_identity_references=(
                    scan.part_id_incomplete_component_identity_references
                ),
                incomplete_pin_inventory_group_count=scan.incomplete_pin_inventory_group_count,
                incomplete_pin_inventory_references=scan.incomplete_pin_inventory_references,
                complete_pin_inventory_group_count=scan.complete_pin_inventory_group_count,
                comparable_pin_group_count=scan.comparable_pin_group_count,
                matching_electrical_type_pin_group_count=(
                    scan.matching_electrical_type_pin_group_count
                ),
                compatible_function_pin_group_count=scan.compatible_function_pin_group_count,
                ambiguous_assignment_pin_group_count=scan.ambiguous_assignment_pin_group_count,
                unambiguous_assignment_pin_group_count=(
                    scan.unambiguous_assignment_pin_group_count
                ),
                candidate_group_count=candidate_count,
                deduplicated_candidate_group_count=scan.deduplicated_candidate_group_count,
                finding_count=finding_count,
                suppressed_candidate_count=candidate_count - finding_count,
            )
        )
    return tuple(result)
