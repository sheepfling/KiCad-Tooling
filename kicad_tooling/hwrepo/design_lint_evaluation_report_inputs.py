"""Build finalized report inputs and early error reports from staged lint state."""

from __future__ import annotations

from .design_lint_evaluation_types import (
    DesignLintEvaluationCandidates,
    DesignLintEvaluationPreparation,
    DesignLintEvaluationReportInput,
    DesignLintFindingDisposition,
)
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import (
    ControlInputBiasHeuristicCoverage,
    DesignLintReport,
)


def evaluation_report_input(
    prepared: DesignLintEvaluationPreparation,
    candidates: DesignLintEvaluationCandidates,
    disposition: DesignLintFindingDisposition,
) -> DesignLintEvaluationReportInput:
    """Combine completed stages into the stable report-assembly input."""
    request = prepared.request
    coverage = prepared.coverage
    return DesignLintEvaluationReportInput(
        project_id=request.project_id,
        coach=request.coach,
        policy=request.policy,
        catalog=prepared.catalog,
        source_hashes=prepared.source_hashes,
        seen=disposition.seen,
        findings=disposition.findings,
        geometry_coverage=coverage.geometry,
        component_role_resolution=prepared.component_role_resolution,
        complementary_alias_resolution=prepared.complementary_alias_resolution,
        i2c_address_coverage=coverage.i2c_address,
        external_protection_coverage=coverage.external_protection,
        crystal_network_coverage=coverage.crystal_network,
        regulator_feedback_coverage=coverage.regulator_feedback,
        rc_filter_coverage=coverage.rc_filter,
        connector_return_distribution_coverage=coverage.connector_return_distribution,
        pcb_decoupling_coverage=coverage.pcb_decoupling,
        pcb_protection_path_coverage=coverage.pcb_protection_path,
        pcb_track_width_coverage=coverage.pcb_track_width,
        pcb_reference_plane_coverage=coverage.pcb_reference_plane,
        pcb_switching_loop_coverage=coverage.pcb_switching_loop,
        pcb_differential_pair_coverage=coverage.pcb_differential_pair,
        pcb_signal_path_coverage=coverage.pcb_signal_path,
        pcb_keepout_coverage=coverage.pcb_keepout,
        pcb_rf_module_antenna_coverage=coverage.pcb_rf_module_antenna,
        stm32_pin_map_coverage=coverage.stm32_pin_map,
        mapped_check_runs=candidates.mapped_check_runs,
        connector_coverage=request.connector_coverage,
        connector_peer_pin_coverage=candidates.connector_peer_pin_coverage,
        component_peer_pin_coverage=candidates.component_peer_pin_coverage,
        digital_peer_voltage_coverage=candidates.digital_peer_voltage_coverage,
        usb_peer_reference_coverage=candidates.usb_peer_reference_coverage,
        serial_peer_reference_coverage=candidates.serial_peer_reference_coverage,
        control_input_bias_coverage=coverage.control_input_bias,
        i2c_pullup_heuristic_coverage=coverage.i2c_pullup_heuristic,
    )


def blocked_wrong_ignore_report(
    prepared: DesignLintEvaluationPreparation,
    candidates: DesignLintEvaluationCandidates,
    issue: str,
) -> DesignLintReport:
    """Explain a fingerprint ignore that points at a different rule."""
    request = prepared.request
    coverage = prepared.coverage
    return DesignLintReport(
        status="BLOCKED",
        project_id=request.project_id,
        source_hashes=prepared.source_hashes,
        netlist_sha256=request.coach.netlist_sha256,
        native_summary=request.coach.native_summary,
        native_status=request.coach.native_status,
        rule_catalog=prepared.catalog,
        schematic_geometry=coverage.geometry,
        i2c_address_coverage=coverage.i2c_address,
        external_protection_coverage=coverage.external_protection,
        crystal_network_coverage=coverage.crystal_network,
        regulator_feedback_coverage=coverage.regulator_feedback,
        rc_filter_coverage=coverage.rc_filter,
        connector_return_distribution=coverage.connector_return_distribution,
        pcb_decoupling=coverage.pcb_decoupling,
        pcb_protection_path=coverage.pcb_protection_path,
        pcb_track_width=coverage.pcb_track_width,
        pcb_reference_plane=coverage.pcb_reference_plane,
        pcb_switching_loop=coverage.pcb_switching_loop,
        pcb_differential_pair_rules=coverage.pcb_differential_pair,
        pcb_signal_path_rules=coverage.pcb_signal_path,
        pcb_keepout_coverage=coverage.pcb_keepout,
        pcb_rf_module_antenna_coverage=coverage.pcb_rf_module_antenna,
        stm32_pin_map_coverage=coverage.stm32_pin_map,
        control_input_bias_coverage=(
            coverage.control_input_bias or ControlInputBiasHeuristicCoverage()
        ),
        i2c_pullup_heuristic_coverage=(
            coverage.i2c_pullup_heuristic or I2cPullupHeuristicCoverage()
        ),
        connector_peer_pin_coverage=candidates.connector_peer_pin_coverage,
        component_peer_pin_coverage=candidates.component_peer_pin_coverage,
        issues=(issue,),
    )
