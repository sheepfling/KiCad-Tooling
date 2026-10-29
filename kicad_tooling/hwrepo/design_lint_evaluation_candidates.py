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
from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_candidate_aggregation import (
    scan_candidate_result,
    validate_catalogued_candidates,
)
from .design_lint_candidate_inputs import (
    ComponentCandidateInputs,
    ConnectorCandidateInputs,
    ControlCandidateInputs,
    DesignLintCandidateInputs,
    MappedCandidateInputs,
    PeerCandidateInputs,
    PowerCandidateInputs,
)
from .design_lint_evaluation_types import (
    DesignLintEvaluationCandidates,
    DesignLintEvaluationPreparation,
)
from .design_lint_mapped_topology_coverage import mapped_topology_coverage_runs
from .design_lint_pcb_inputs import PcbCandidateInputs
from .design_lint_peer_evaluation import scan_peer_design_lint_evidence
from .design_lint_power_regulator_passives import regulator_required_passive_candidates
from .i2c_address_inputs import I2cAddressCandidateInput
from .i2c_peer_reference_coverage import i2c_peer_reference_coverage
from .i2c_pullup_inputs import I2cPullupSnifferInput
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
    scan_result = scan_candidate_result(
        DesignLintCandidateInputs(
            observed=observed,
            catalog=prepared.catalog,
            schematic_geometry=request.schematic_geometry,
            reviewed_connector_references=peer_evidence.reviewed_connector_references,
            connector=ConnectorCandidateInputs(
                coverage=request.connector_coverage,
                return_distribution=coverage.connector_return_distribution,
                stateful_contact_map=policy.connector_stateful_contact_map,
                power_output_review_enabled=connector_power_output_mode != "off",
            ),
            component=ComponentCandidateInputs(
                peer_pin_assignment_scans=peer_evidence.peer_pin_assignment_scans,
                peer_power_output_review_enabled=peer_power_output_mode != "off",
            ),
            control=ControlCandidateInputs.from_legacy_arguments(
                observed,
                coverage.control_input_bias,
            ),
            power=PowerCandidateInputs(
                component_role_map=policy.component_role_map,
                power_path_map=policy.power_path_map,
                power_sequence_map=policy.power_sequence_map,
                oscillator_output_path_map=policy.oscillator_output_path_map,
                ic_decoupling_map=policy.ic_decoupling_map,
            ),
            bus=BusCandidateInputs(
                observed=observed,
                i2c_address=I2cAddressCandidateInput.from_candidate_arguments(
                    observed, policy.i2c_address_map, coverage.i2c_address
                ),
                i2c_pullup=I2cPullupSnifferInput.from_legacy_arguments(
                    observed, coverage.i2c_pullup_heuristic
                ),
                complementary_alias_resolution=prepared.complementary_alias_resolution,
                i2c_peer_reference_scan=peer_evidence.i2c_peer_reference_scan,
                spi_roster=request.spi_roster,
                spi_peer_reference_scan=peer_evidence.spi_peer_reference_scan,
                can_peer_reference_scan=peer_evidence.can_peer_reference_scan,
                rs485_peer_reference_scan=peer_evidence.rs485_peer_reference_scan,
                pcb_differential_pair_rule_map=policy.pcb_differential_pair_rule_map,
                reviewed_connector_references=peer_evidence.reviewed_connector_references,
            ),
            peer=PeerCandidateInputs(
                digital_voltage_context=request.digital_peer_voltage_context,
                digital_voltage_scan=peer_evidence.digital_peer_voltage_scan,
                usb_reference_scan=peer_evidence.usb_peer_reference_scan,
                serial_reference_scan=peer_evidence.serial_peer_reference_scan,
                serial_roster=request.serial_peer_roster,
                usb_c_port_roster=request.usb_c_port_roster,
            ),
            mapped=MappedCandidateInputs(
                external_protection=coverage.external_protection,
                crystal_network=coverage.crystal_network,
                regulator_feedback=coverage.regulator_feedback,
                rc_filter=coverage.rc_filter,
            ),
            pcb=PcbCandidateInputs(
                component_inventory=coverage.pcb_component_inventory,
                decoupling=coverage.pcb_decoupling,
                protection_path=coverage.pcb_protection_path,
                track_width=coverage.pcb_track_width,
                reference_plane=coverage.pcb_reference_plane,
                switching_loop=coverage.pcb_switching_loop,
                differential_pair=coverage.pcb_differential_pair,
                signal_path=coverage.pcb_signal_path,
                keepout=coverage.pcb_keepout,
                rf_antenna=coverage.pcb_rf_module_antenna,
                touch_pad_clearance=coverage.pcb_touch_pad_clearance,
                stm32_pin_map=coverage.stm32_pin_map,
            ),
            usb_data_path_map=policy.usb_data_path_map,
            additional_candidates=(
                *request.pcb_dru_rule_candidates,
                *request.pcb_native_drc_candidates,
            ),
        )
    )
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
