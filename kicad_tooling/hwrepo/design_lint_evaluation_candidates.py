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
from .design_lint_candidate_aggregation import candidates
from .design_lint_evaluation_types import (
    DesignLintEvaluationCandidates,
    DesignLintEvaluationPreparation,
)
from .design_lint_mapped_topology_coverage import mapped_topology_coverage_runs
from .design_lint_peer_evaluation import scan_peer_design_lint_evidence
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
        rs485_peer_reference_context=request.rs485_peer_reference_context,
        usb_data_path_map=policy.usb_data_path_map,
        default_modes=prepared.default_modes,
        overrides=prepared.overrides,
    )
    peer_power_output_override = prepared.overrides.get("component.peer_power_output_unconnected")
    peer_power_output_mode = (
        peer_power_output_override.mode
        if peer_power_output_override is not None
        else prepared.default_modes["component.peer_power_output_unconnected"]
    )
    connector_power_output_override = prepared.overrides.get("connector.unconnected_power_output")
    connector_power_output_mode = (
        connector_power_output_override.mode
        if connector_power_output_override is not None
        else prepared.default_modes["connector.unconnected_power_output"]
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
        pcb_component_inventory_coverage=coverage.pcb_component_inventory,
        connector_coverage=request.connector_coverage,
        digital_peer_voltage_scan=peer_evidence.digital_peer_voltage_scan,
        usb_peer_reference_scan=peer_evidence.usb_peer_reference_scan,
        serial_peer_reference_scan=peer_evidence.serial_peer_reference_scan,
        i2c_peer_reference_scan=peer_evidence.i2c_peer_reference_scan,
        spi_peer_reference_scan=peer_evidence.spi_peer_reference_scan,
        can_peer_reference_scan=peer_evidence.can_peer_reference_scan,
        rs485_peer_reference_scan=peer_evidence.rs485_peer_reference_scan,
        peer_pin_assignment_scans=peer_evidence.peer_pin_assignment_scans,
        peer_power_output_review_enabled=peer_power_output_mode != "off",
        connector_power_output_review_enabled=connector_power_output_mode != "off",
    )
    i2c_peer_coverage = None
    spi_peer_coverage = None
    can_peer_coverage = None
    rs485_peer_coverage = None
    if coach.netlist_sha256 is not None:
        i2c_candidate_bus_keys = frozenset(
            (
                item.evidence["SDA"][0].casefold(),
                item.evidence["SCL"][0].casefold(),
            )
            for item in items
            if item.rule_id == "bus.i2c_peer_reference_review"
        )
        i2c_peer_coverage = i2c_peer_reference_coverage(
            peer_evidence.i2c_peer_reference_scan,
            prepared.default_modes,
            prepared.overrides,
            coach.netlist_sha256,
            candidate_bus_keys=i2c_candidate_bus_keys,
        )
        spi_candidate_clock_keys = frozenset(
            item.evidence["SCK"][0].casefold()
            for item in items
            if item.rule_id == "bus.spi_peer_reference_review"
        )
        spi_peer_coverage = spi_peer_reference_coverage(
            peer_evidence.spi_peer_reference_scan,
            prepared.default_modes,
            prepared.overrides,
            coach.netlist_sha256,
            candidate_clock_keys=spi_candidate_clock_keys,
        )
        can_candidate_bus_keys = frozenset(
            (
                item.evidence["CANH"][0].casefold(),
                item.evidence["CANL"][0].casefold(),
            )
            for item in items
            if item.rule_id == "bus.can_peer_reference_review"
        )
        can_peer_coverage = can_peer_reference_coverage(
            peer_evidence.can_peer_reference_scan,
            prepared.default_modes,
            prepared.overrides,
            coach.netlist_sha256,
            candidate_bus_keys=can_candidate_bus_keys,
        )
        rs485_candidate_keys = frozenset(
            (
                item.evidence["bus"][0].casefold(),
                item.evidence["pair"][0].casefold(),
            )
            for item in items
            if item.rule_id == "bus.rs485_peer_reference_review"
        )
        rs485_peer_coverage = rs485_peer_reference_coverage(
            peer_evidence.rs485_peer_reference_scan,
            prepared.default_modes,
            prepared.overrides,
            coach.netlist_sha256,
            candidate_keys=rs485_candidate_keys,
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
        i2c_peer_reference_coverage=i2c_peer_coverage,
        spi_peer_reference_coverage=spi_peer_coverage,
        can_peer_reference_coverage=can_peer_coverage,
        rs485_peer_reference_coverage=rs485_peer_coverage,
        mapped_check_runs=mapped_topology_coverage_runs(
            policy, prepared.default_modes, items, coach.netlist_sha256
        ),
    )
