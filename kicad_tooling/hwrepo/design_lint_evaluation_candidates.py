"""Run theme candidate analyzers and source-bound peer coverage checks."""

from __future__ import annotations

from .can_peer_reference_coverage import can_peer_reference_coverage
from .component_peer_pin_coverage import (
    component_peer_pin_rule_coverage as resolve_component_peer_pin_rule_coverage,
)
from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_peer_pin_coverage import connector_peer_pin_heuristic_coverage
from .design_lint_candidate_aggregation import (
    scan_candidate_result,
    validate_catalogued_candidates,
)
from .design_lint_evaluation_types import (
    DesignLintEvaluationCandidates,
    DesignLintEvaluationPreparation,
)
from .design_lint_mapped_topology_coverage import mapped_topology_coverage_runs
from .design_lint_power_regulator_passives import regulator_required_passive_candidates
from .i2c_peer_reference_coverage import i2c_peer_reference_coverage
from .rs485_peer_reference_coverage import rs485_peer_reference_coverage
from .spi_peer_reference_coverage import spi_peer_reference_coverage


def scan_evaluation_candidates(
    prepared: DesignLintEvaluationPreparation,
) -> DesignLintEvaluationCandidates:
    """Collect theme findings and the matching connector, peer, and map coverage."""
    request = prepared.request
    coach = request.coach
    policy = request.policy
    candidate_inputs = prepared.candidate_inputs
    peer_evidence = prepared.peer_evidence
    observed = candidate_inputs.observed
    scan_result = scan_candidate_result(candidate_inputs)
    items = scan_result.candidates
    items = (
        *items,
        *regulator_required_passive_candidates(observed, policy.regulator_passive_topology_map),
    )
    items = tuple(
        sorted(
            items,
            key=lambda item: (item.rule_id, item.subject),
        )
    )
    validate_catalogued_candidates(items, prepared.catalog)
    i2c_peer_coverage = None
    spi_peer_coverage = None
    can_peer_coverage = None
    rs485_peer_coverage = None
    if coach.netlist_sha256 is not None:
        peer_keys = scan_result.peer_reference_keys
        i2c_peer_coverage = i2c_peer_reference_coverage(
            peer_evidence.i2c_peer_reference_scan,
            prepared.default_modes,
            prepared.overrides,
            coach.netlist_sha256,
            candidate_bus_keys=peer_keys.i2c_buses,
        )
        spi_peer_coverage = spi_peer_reference_coverage(
            peer_evidence.spi_peer_reference_scan,
            prepared.default_modes,
            prepared.overrides,
            coach.netlist_sha256,
            candidate_clock_keys=peer_keys.spi_clocks,
        )
        can_peer_coverage = can_peer_reference_coverage(
            peer_evidence.can_peer_reference_scan,
            prepared.default_modes,
            prepared.overrides,
            coach.netlist_sha256,
            candidate_bus_keys=peer_keys.can_buses,
        )
        rs485_peer_coverage = rs485_peer_reference_coverage(
            peer_evidence.rs485_peer_reference_scan,
            prepared.default_modes,
            prepared.overrides,
            coach.netlist_sha256,
            candidate_keys=peer_keys.rs485_pairs,
        )
    connector_peer_pin_coverage = (
        None
        if coach.netlist_sha256 is None
        else connector_peer_pin_heuristic_coverage(
            observed,
            coach.netlist_sha256,
            peer_evidence.reviewed_connector_references,
            source_matched_connector_pin_evidence(observed, request.connector_coverage),
            source_matched_connector_peer_assignment_groups(observed, request.connector_coverage),
            finding_counts=scan_result.connector_peer_pin_finding_counts,
        )
    )
    component_peer_pin_coverage = (
        ()
        if coach.netlist_sha256 is None
        else resolve_component_peer_pin_rule_coverage(
            peer_evidence.peer_pin_assignment_scans,
            prepared.default_modes,
            prepared.overrides,
            items,
            coach.netlist_sha256,
        )
    )
    return DesignLintEvaluationCandidates(
        items=items,
        connector_peer_pin_coverage=connector_peer_pin_coverage,
        component_peer_pin_coverage=component_peer_pin_coverage,
        digital_peer_voltage_coverage=peer_evidence.digital_peer_voltage_coverage,
        usb_peer_reference_coverage=peer_evidence.usb_peer_reference_coverage,
        serial_peer_reference_coverage=peer_evidence.serial_peer_reference_coverage,
        i2c_peer_reference_coverage=i2c_peer_coverage,
        spi_peer_reference_coverage=spi_peer_coverage,
        can_peer_reference_coverage=can_peer_coverage,
        rs485_peer_reference_coverage=rs485_peer_coverage,
        mapped_check_runs=mapped_topology_coverage_runs(
            policy, prepared.default_modes, items, coach.netlist_sha256
        ),
    )
