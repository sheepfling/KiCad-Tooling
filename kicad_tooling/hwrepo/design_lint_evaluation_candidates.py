"""Run theme candidate analyzers and source-bound peer coverage checks."""

from __future__ import annotations

from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_peer_pin_coverage import connector_peer_pin_heuristic_coverage
from .design_lint_candidate_aggregation import candidates
from .design_lint_evaluation_types import (
    DesignLintEvaluationCandidates,
    DesignLintEvaluationPreparation,
)
from .design_lint_mapped_topology_coverage import mapped_topology_coverage_runs
from .design_lint_peer_coverage import (
    component_peer_pin_rule_coverage as resolve_component_peer_pin_rule_coverage,
)
from .design_lint_peer_evaluation import scan_peer_design_lint_evidence


def scan_evaluation_candidates(
    prepared: DesignLintEvaluationPreparation,
) -> DesignLintEvaluationCandidates:
    """Collect theme findings and the matching connector, peer, and map coverage."""
    request = prepared.request
    coach = request.coach
    policy = request.policy
    coverage = prepared.coverage
    observed = coach.observed
    if observed is None:
        raise RuntimeError("Candidate evaluation requires prepared native netlist evidence")
    peer_evidence = scan_peer_design_lint_evidence(
        observed=observed,
        netlist_sha256=coach.netlist_sha256,
        connector_coverage=request.connector_coverage,
        digital_peer_voltage_context=request.digital_peer_voltage_context,
        serial_peer_roster=request.serial_peer_roster,
        usb_data_path_map=policy.usb_data_path_map,
        default_modes=prepared.default_modes,
        overrides=prepared.overrides,
    )
    items = candidates(
        observed,
        prepared.catalog,
        request.schematic_geometry,
        coverage.i2c_address,
        coverage.external_protection,
        coverage.crystal_network,
        coverage.regulator_feedback,
        coverage.rc_filter,
        coverage.connector_return_distribution,
        coverage.pcb_decoupling,
        coverage.pcb_protection_path,
        coverage.pcb_track_width,
        coverage.pcb_switching_loop,
        coverage.pcb_differential_pair,
        policy.pcb_differential_pair_rule_map,
        policy.i2c_address_map,
        policy.usb_data_path_map,
        coverage.stm32_pin_map,
        request.spi_roster,
        request.usb_c_port_roster,
        policy.power_path_map,
        policy.power_sequence_map,
        coverage.pcb_reference_plane,
        coverage.control_input_bias,
        coverage.i2c_pullup_heuristic,
        request.digital_peer_voltage_context,
        policy.component_role_map,
        request.serial_peer_roster,
        peer_evidence.reviewed_connector_references,
        prepared.complementary_alias_resolution,
        pcb_signal_path_coverage=coverage.pcb_signal_path,
        pcb_keepout_coverage=coverage.pcb_keepout,
        pcb_rf_module_antenna_coverage=coverage.pcb_rf_module_antenna,
        connector_coverage=request.connector_coverage,
        digital_peer_voltage_scan=peer_evidence.digital_peer_voltage_scan,
        usb_peer_reference_scan=peer_evidence.usb_peer_reference_scan,
        serial_peer_reference_scan=peer_evidence.serial_peer_reference_scan,
        peer_pin_assignment_scans=peer_evidence.peer_pin_assignment_scans,
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
            repeated_function_finding_count=sum(
                item.rule_id == "connector.repeated_pin_function" for item in items
            ),
            peer_pin_outlier_finding_count=sum(
                item.rule_id == "connector.peer_pin_assignment_outlier" for item in items
            ),
            peer_pin_divergence_finding_count=sum(
                item.rule_id == "connector.peer_pin_assignment_divergence" for item in items
            ),
            part_id_peer_pin_outlier_finding_count=sum(
                item.rule_id == "connector.peer_pin_assignment_outlier"
                and item.evidence.get("peer_identity_basis") == ("part_id",)
                for item in items
            ),
            part_id_peer_pin_divergence_finding_count=sum(
                item.rule_id == "connector.peer_pin_assignment_divergence"
                and item.evidence.get("peer_identity_basis") == ("part_id",)
                for item in items
            ),
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
        mapped_check_runs=mapped_topology_coverage_runs(
            policy, prepared.default_modes, items, coach.netlist_sha256
        ),
    )
